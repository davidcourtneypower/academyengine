"""Academy Engine bridge service for the v1.24 runtime.

Active production ownership:
- PlayStyle / PlayStyle+ / newgen PlayStyle enrichment
- Role+ -> Role++

FC27 native ownership (observation only):
- potential / Dynamic Potential
- attribute growth, maturation and ageing
"""
from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from dataclasses import dataclass
import json, time, traceback
from .file_bridge import FileBridge, PROTOCOL_VERSION
from .world_bootstrap_store import WorldBootstrapStore
from .playstyle_development_planner import audit_world as audit_playstyles
from .playstyle_acquisition_control import audit_world as audit_ps_acquisition
from .playstyle_plus_acquisition_control import audit_world as audit_ps_plus_acquisition
from .role_acquisition_control import audit_world as audit_role_acquisition
from .season_generation_audit import audit_world as audit_generation
from .newgen_playstyle_enrichment import audit_world as audit_newgen_enrichment
from .season_lifecycle_audit import audit_world as audit_season_lifecycle
from .live_playstyle_writer import stage_bundle as stage_live_evolution_bundle
from .save_context import ensure_save_context
from .branch_identity import resolve_branch, write_active_context, activate_exact_save_branch
from .playstyle_lifetime import audit_world as audit_playstyle_lifetime
from .runtime_config import normal_cooldown_days, plus_cooldown_days, role_cooldown_days
from .paths import ACADEMY_STATE_ROOT
from .save_restore_points import create_restore_point
from .transaction_store import set_lifecycle, record_game_snapshot, restore_exact_save_anchor, upsert_save_anchor, find_exact_save_anchor

SUPPORTED_KINDS={"PING","CHECKPOINT_READY","CHECKPOINT_SNAPSHOT"}
# Snapshots that may represent FC27 loading a save file (exact-save lookup applies).
LOAD_TRIGGERS={"CAREER_SETTLED_BASELINE","SCREEN_LOADED_BASELINE","INITIAL_BASELINE","LOAD_RECONCILED","BOUNDARY_RESYNC"}
# Snapshots that are genuine FC27 save/load states and therefore become save anchors.
ANCHOR_TRIGGERS={"CAREER_SETTLED_BASELINE","SCREEN_LOADED_BASELINE","INITIAL_BASELINE","PREPARE_FOR_SAVE","SAVE_STABILIZED","LOAD_RECONCILED"}
OUTFIELD=("crossing","finishing","headingaccuracy","shortpassing","volleys","defensiveawareness","standingtackle","slidingtackle","dribbling","curve","freekickaccuracy","longpassing","ballcontrol","shotpower","jumping","stamina","strength","longshots","acceleration","sprintspeed","agility","reactions","balance","aggression","composure","interceptions","positioning","vision","penalties")
GK=("gkdiving","gkhandling","gkkicking","gkpositioning","gkreflexes")

def validate_snapshot(payload):
    players=payload.get("players")
    if not isinstance(players,list): return False,"PLAYERS_NOT_LIST",0
    seen=set()
    for p in players:
        if not isinstance(p,dict): return False,"PLAYER_NOT_OBJECT",0
        pid=p.get("playerid"); pos=p.get("preferredposition1"); attrs=p.get("attributes")
        if not isinstance(pid,int) or pid<460000 or pid in seen: return False,"BAD_PLAYER_ID",0
        seen.add(pid)
        if not isinstance(attrs,dict): return False,"ATTRIBUTES_NOT_OBJECT",0
        needed=GK if pos==0 else OUTFIELD
        if any(k not in attrs or not isinstance(attrs[k],(int,float)) for k in needed): return False,"INCOMPLETE_PRIMARY_ATTRIBUTES",0
    return True,"OK",len(players)

@dataclass
class BridgeService:
    bridge: FileBridge

    _CHECKPOINT_STAGES = (
        "Validating career snapshot",
        "Resolving career branch",
        "Loading persistent career state",
        "Reconciling player development",
        "Checking PlayStyle development",
        "Checking Role development",
        "Checking new generated players",
        "Checking season lifecycle",
        "Ranking PlayStyle candidates",
        "Ranking PlayStyle+ candidates",
        "Ranking Role++ candidates",
        "Preparing verified game updates",
        "Finalising Academy Engine data",
    )

    def _progress(self, req, stage_index:int, *, player_count:int|None=None, detail:str|None=None):
        total=len(self._CHECKPOINT_STAGES)
        idx=max(1,min(int(stage_index),total))
        payload={
            "state":"RUNNING",
            "task":req.kind,
            "trigger":str((req.payload or {}).get("trigger") or req.kind),
            "request_id":req.request_id,
            "started_at":getattr(self,"_active_started_at",time.time()),
            "stage_index":idx,
            "stage_total":total,
            "stage":self._CHECKPOINT_STAGES[idx-1],
            "remaining":max(0,total-idx),
        }
        if player_count is not None:
            payload["player_count"]=int(player_count)
        if detail:
            payload["detail"]=str(detail)
        self._activity(**payload)

    def handle(self,req):
        if req.kind=="PING":
            return {"status":"OK","payload":{"reply":"PONG","protocol":PROTOCOL_VERSION,"production":"PLAYSTYLE_ROLE_ONLY","native_ownership":"POTENTIAL_ATTRIBUTES_AGEING","writes_locked":False,"request_echo":req.payload.get("token")}}
        if req.kind=="CHECKPOINT_READY":
            return {"status":"OK","payload":{"accepted":True,"checkpoint_id":req.payload.get("checkpoint_id"),"production":"PLAYSTYLE_ROLE_ONLY","writes_locked":False}}
        if req.kind!="CHECKPOINT_SNAPSHOT":
            return {"status":"HOLD","payload":{"reason":"UNSUPPORTED_KIND","writes_locked":True}}

        try:
            set_lifecycle('RECONCILING', detail='Validating FC27 career snapshot', runtime_session=str(req.payload.get('runtime_session') or ''), career_uid=str(req.payload.get('save_uid') or ''), request_id=req.request_id, career_date=((req.payload.get('career') or {}).get('date') or {}), snapshot_sequence=int(req.payload.get('snapshot_sequence') or req.payload.get('day_epoch') or 0))
        except Exception:
            pass
        self._progress(req,1)
        ok,reason,count=validate_snapshot(req.payload)
        if not ok:
            return {"status":"HOLD","payload":{"accepted":False,"reason":reason,"player_count":count,"checkpoint_id":req.payload.get("checkpoint_id"),"writes_locked":True}}
        save_uid=req.payload.get("save_uid")
        if save_uid is None or str(save_uid).strip()=="":
            return {"status":"HOLD","payload":{"accepted":False,"reason":"MISSING_SAVE_UID","player_count":count,"checkpoint_id":req.payload.get("checkpoint_id"),"writes_locked":True}}

        timings={}; store=WorldBootstrapStore(ACADEMY_STATE_ROOT)
        self._progress(req,2,player_count=count)
        trigger_upper=str(req.payload.get("trigger") or "").upper()
        exact_known={"status":"NOT_CHECKED"}
        if trigger_upper in LOAD_TRIGGERS:
            try: exact_known=find_exact_save_anchor(req.payload,anchors_only=(trigger_upper=="BOUNDARY_RESYNC"))
            except Exception as exc: exact_known={"status":"ERROR","reason":str(exc)}
        if exact_known.get("status")=="FOUND":
            branch=activate_exact_save_branch(ACADEMY_STATE_ROOT,career_uid=str(save_uid),players=req.payload["players"],runtime_session=req.payload.get("runtime_session"),career_date=(req.payload.get("career") or {}).get("date"),fingerprint=str(exact_known.get("fingerprint") or ''),source_storage_key=str(exact_known.get("storage_key") or ''))
        else:
            branch=resolve_branch(ACADEMY_STATE_ROOT,career_uid=str(save_uid),players=req.payload["players"],runtime_session=req.payload.get("runtime_session"),trigger=req.payload.get("trigger"),hints_root=self.bridge.root,career_date=(req.payload.get("career") or {}).get("date"))
        if branch.get("status")!="OK":
            write_active_context(self.bridge.root,career_uid=str(save_uid),runtime_session=str(req.payload.get('runtime_session') or ''),writes_held=True,reason=str(branch.get("reason") or "BRANCH_UNRESOLVED"))
            return {"status":"HOLD","payload":{"accepted":False,"reason":branch.get("reason","BRANCH_UNRESOLVED"),"player_count":count,"checkpoint_id":req.payload.get("checkpoint_id"),"save_uid":str(save_uid),"branch_resolution":branch,"writes_locked":True}}
        storage_key=str(branch["storage_key"]); branch_id=str(branch["branch_id"])
        try:
            set_lifecycle('RECONCILING', detail='Loading Academy Engine career state', runtime_session=str(req.payload.get('runtime_session') or ''), career_uid=str(save_uid), storage_key=storage_key, branch_id=branch_id, request_id=req.request_id, career_date=((req.payload.get('career') or {}).get('date') or {}), snapshot_sequence=int(req.payload.get('snapshot_sequence') or req.payload.get('day_epoch') or 0))
        except Exception:
            pass
        self._progress(req,3,player_count=count)
        exact_anchor={"status":"NOT_CHECKED"}
        if trigger_upper in LOAD_TRIGGERS:
            try:
                exact_anchor=restore_exact_save_anchor(payload=req.payload,storage_key=storage_key,branch_id=branch_id,anchors_only=(trigger_upper=="BOUNDARY_RESYNC"))
            except Exception as exc:
                exact_anchor={"status":"ERROR","reason":str(exc)}
        # Exact load restoration can create the target world before context setup.
        # Settings remain user policy and must follow its confirmed source separately.
        from .save_context import inherit_settings
        settings_source=exact_anchor.get('anchor_storage_key') or branch.get('source_storage_key') or branch.get('parent_storage_key')
        inherit_settings(ACADEMY_STATE_ROOT,settings_source,storage_key)
        save_context=ensure_save_context(self.bridge.root,ACADEMY_STATE_ROOT,save_uid=str(save_uid),runtime_session=req.payload.get("runtime_session"),players=req.payload["players"],store=store,storage_key=storage_key,branch_id=branch_id,parent_storage_key=branch.get("parent_storage_key"),rollback_from_storage_key=branch.get("rollback_from_storage_key"),rollback_date=branch.get("rollback_date") or (req.payload.get("career") or {}).get("date"))
        write_active_context(self.bridge.root,career_uid=str(save_uid),branch_id=branch_id,storage_key=storage_key,runtime_session=str(req.payload.get('runtime_session') or ''),writes_held=False,reason=str(branch.get("state") or "OK"))
        # v1.24.24: re-read settings for the career that is now active. The 1 s settings
        # cache could otherwise serve the previous save's values to this checkpoint, and
        # PS+ eligibility is fixed permanently when a player is first found.
        from .runtime_config import load_runtime_settings
        load_runtime_settings(force=True)
        self._progress(req,4,player_count=count,detail=f"Reconciling {count:,} tracked snapshot players")
        t0=time.perf_counter()
        # Growth is credited only on an unbroken timeline: same active branch, no
        # rewind/load/Save-As resolution and no exact-save restore this snapshot.
        branch_state=str(branch.get("state") or "")
        credit_development=(branch_state=="CONTINUE_ACTIVE_BRANCH" and exact_anchor.get("status")!="RESTORED")
        adopted=store.ingest(storage_key,req.payload["players"],req.payload.get("checkpoint_id"),request_id=req.request_id,runtime_session=req.payload.get("runtime_session"),day_epoch=req.payload.get("day_epoch"),career_uid=str(save_uid),branch_id=branch_id,career_meta=req.payload.get("career"),trigger=req.payload.get("trigger"),credit_development=credit_development)
        timings["ingest_ms"]=round((time.perf_counter()-t0)*1000,1)
        # v1.24.26: Role++ upgrades FC27 made itself are recorded as events (no cooldown).
        if isinstance(adopted,dict) and adopted.get("native_role_upgrades"):
            try:
                from .event_engine import record_native_role_upgrades
                record_native_role_upgrades(storage_key,adopted["native_role_upgrades"],career=req.payload.get("career") or {})
            except Exception:
                pass

        playstyle_plan={"ps_tracked":0,"ps_progressing":0,"ps_ready":0,"ps_plus_ready":0,"max_ps_progress":0.0,"max_ps_plus_progress":0.0}
        generation_audit={"checkpoint_new":0}; newgen_enrichment={"checkpoint_new":0,"enrichment_proposals":0}
        season_lifecycle={"status":"NOT_EVALUATED"}
        ps_acquisition={"ready_paths":0,"ready_players":0,"winner_count":0,"production_eligible":0,"cooldown_days":normal_cooldown_days()}
        ps_plus_acquisition={"ready_paths":0,"ready_players":0,"winner_count":0,"production_eligible":0,"cooldown_days":plus_cooldown_days()}
        role_acquisition={"ready_paths":0,"ready_players":0,"winner_count":0,"production_eligible":0,"cooldown_days":role_cooldown_days()}
        playstyle_lifetime={"observed":0,"absolute_normal_cap":7,"normal_cap_hist":{},"plus_eligible":0,"plus_eligible_pct":0.0,"plus_cap":1}
        live_write={"status":"NOT_EVALUATED","staged":0}

        if adopted.get("reconciled",True) and adopted.get("status") != "IDEMPOTENT_NOOP":
            world=getattr(store,"last_world",None) or json.loads(store.path_for(storage_key).read_text(encoding="utf-8"))
            ta=time.perf_counter()
            self._progress(req,5,player_count=count)
            playstyle_plan=audit_playstyles(world)
            self._progress(req,6,player_count=count)
            # Role evidence is evaluated as part of the shared development/aquisition model.
            self._progress(req,7,player_count=count)
            generation_audit=audit_generation(world,req.payload.get("checkpoint_id"))
            newgen_enrichment=audit_newgen_enrichment(world,req.payload.get("checkpoint_id"))
            self._progress(req,8,player_count=count)
            season_lifecycle=audit_season_lifecycle(world,adopted)
            self._progress(req,9,player_count=count)
            ps_acquisition=audit_ps_acquisition(world)
            self._progress(req,10,player_count=count)
            ps_plus_acquisition=audit_ps_plus_acquisition(world)
            self._progress(req,11,player_count=count)
            role_acquisition=audit_role_acquisition(world)
            playstyle_lifetime=audit_playstyle_lifetime(world)
            self._progress(req,12,player_count=count,detail="Building receipt-gated FC27 changes")
            live_write=stage_live_evolution_bundle(self.bridge.root,world,ps_acquisition,ps_plus_acquisition,newgen_enrichment,role_acquisition,checkpoint_id=str(req.payload.get("checkpoint_id")))
            timings["audits_ms"]=round((time.perf_counter()-ta)*1000,1)

        self._progress(req,13,player_count=count)
        try:
            journal_payload=dict(req.payload); journal_payload['request_id']=req.request_id
            record_game_snapshot(payload=journal_payload,storage_key=storage_key,branch_id=branch_id)
        except Exception:
            pass
        restore_point={}
        save_anchor={"status":"NOT_WRITTEN"}
        if adopted.get("reconciled",True):
            try:
                restore_point=create_restore_point(storage_key,trigger=str(req.payload.get("trigger") or "CHECKPOINT"),request_id=req.request_id)
            except Exception as exc:
                restore_point={"status":"ERROR","reason":str(exc)}
            # Baseline/load/save snapshots are exact FC27 save-state anchors. They
            # let Academy Engine discard progression from a timeline the user never
            # saved, including reloads where the FC27 career date itself did not change.
            # A boundary re-sync is anchored only when it did not continue the active
            # branch (i.e. it looked like a real load); ordinary re-syncs are not saves.
            if trigger_upper in ANCHOR_TRIGGERS or (trigger_upper=="BOUNDARY_RESYNC" and (branch_state!="CONTINUE_ACTIVE_BRANCH" or exact_anchor.get("status")=="RESTORED")):
                try:
                    save_anchor=upsert_save_anchor(payload=req.payload,storage_key=storage_key,branch_id=branch_id,trigger=trigger_upper)
                except Exception as exc:
                    save_anchor={"status":"ERROR","reason":str(exc)}

        payload={
            "accepted":bool(adopted.get("reconciled",True)),"reason":"OK" if adopted.get("reconciled",True) else "RECONCILIATION_FAILED",
            "player_count":count,"checkpoint_id":req.payload.get("checkpoint_id"),"save_uid":str(save_uid),"career_uid":str(save_uid),"career":req.payload.get("career") or {},"branch_id":branch_id,"storage_key":storage_key,"branch_resolution":branch,"exact_save_lookup":exact_known,"bootstrap":adopted,"save_context":save_context,
            "native_ownership":{"dynamic_potential":"FC27","attributes":"FC27","ageing":"FC27","academy_engine_writes":False},
            "playstyle_plan":playstyle_plan,
            "generation_audit":generation_audit,"newgen_enrichment":newgen_enrichment,
            "season_lifecycle":season_lifecycle,"ps_acquisition":ps_acquisition,"ps_plus_acquisition":ps_plus_acquisition,
            "role_acquisition":role_acquisition,"playstyle_lifetime":playstyle_lifetime,"live_write":live_write,"restore_point":restore_point,"exact_save_anchor":exact_anchor,"save_anchor":save_anchor,"timings":timings,
            "production_families":["PLAYSTYLE","PLAYSTYLE_PLUS","ROLE"],"writes_locked":False,
        }
        try:
            set_lifecycle('RECONCILING' if adopted.get('reconciled',True) else 'ERROR', detail='Building complete overlay read model' if adopted.get('reconciled',True) else 'Career reconciliation failed', runtime_session=str(req.payload.get('runtime_session') or ''), career_uid=str(save_uid), storage_key=storage_key, branch_id=branch_id, request_id=req.request_id, career_date=((req.payload.get('career') or {}).get('date') or {}), snapshot_sequence=int(req.payload.get('snapshot_sequence') or req.payload.get('day_epoch') or 0))
        except Exception:
            pass
        return {"status":"OK" if adopted.get("reconciled",True) else "HOLD","payload":payload}

    def _activity(self, **payload):
        """Publish a tiny activity channel independently of the full read model.

        Heavy checkpoint reconciliation intentionally blocks full overlay publication.
        The native external overlay polls this small file directly so it can lock input
        and display REFRESHING/LOADING progress immediately, while continuing to render
        the previous immutable read generation underneath.
        """
        path=self.bridge.root / "bridge_activity.json"
        tmp=path.with_suffix(path.suffix+".tmp")
        txt_path=self.bridge.root / "overlay_activity.txt"
        txt_tmp=txt_path.with_suffix(txt_path.suffix+".tmp")
        try:
            tmp.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
            replace_retry(tmp,path)
        except Exception:
            pass
        try:
            running=str(payload.get("state") or "").upper()=="RUNNING"
            trigger=str(payload.get("trigger") or "").upper()
            if trigger in {"CAREER_SETTLED_BASELINE","INITIAL_BASELINE","SCREEN_LOADED_BASELINE"}:
                title="LOADING CAREER DATA"
            elif trigger in {"DAY_PASSED","DAY_SETTLED","SAVE_STABILIZED","CAREER_ADVANCE","BOUNDARY_RESYNC"}:
                title="REFRESHING CAREER DATA"
            elif trigger in {"PREPARE_FOR_SAVE","SAVE"}:
                title="SAVING ACADEMY ENGINE DATA"
            else:
                title="PROCESSING CAREER DATA"
            stage=str(payload.get("stage") or payload.get("detail") or "")
            # Never expose raw Live Editor event/request identifiers in the user-facing
            # processing card. Those remain available in diagnostics/logs only.
            low_stage=stage.lower()
            if "careermodeevent:" in low_stage or "eventid" in low_stage or "event_id" in low_stage:
                stage="Waiting for FC27 to publish the settled career snapshot."
            if not stage and running:
                stage="Academy Engine is reconciling the latest FC27 career state."
            safe=lambda v: str(v or "").replace("\r"," ").replace("\n"," ").replace("=","-")
            text="\n".join([
                f"RUNNING={1 if running else 0}",
                f"TITLE={safe(title if running else '')}",
                f"DETAIL={safe(stage if running else '')}",
                f"STAGE_INDEX={int(payload.get('stage_index') or 0)}",
                f"STAGE_TOTAL={int(payload.get('stage_total') or 0)}",
                f"REQUEST_ID={safe(payload.get('request_id') or '')}",
            ])+"\n"
            txt_tmp.write_text(text,encoding="utf-8")
            replace_retry(txt_tmp,txt_path)
        except Exception:
            pass

    def _session_status(self, result, req):
        if req.kind != "CHECKPOINT_SNAPSHOT": return
        payload=result.get("payload") or {}
        path=self.bridge.root / "career_session_status.json"
        tmp=path.with_suffix(path.suffix+".tmp")
        obj={
            "state":"ACTIVE" if result.get("status")=="OK" else "SYNCING",
            "timestamp":time.time(),
            "request_id":req.request_id,
            "save_uid":str(payload.get("save_uid") or req.payload.get("save_uid") or ""),
            "storage_key":str(payload.get("storage_key") or ""),
            "branch_id":str(payload.get("branch_id") or ""),
            "career_date":((payload.get("career") or req.payload.get("career") or {}).get("date") or {}),
            "trigger":str(req.payload.get("trigger") or ""),
            "reason":str(payload.get("reason") or ""),
        }
        try:
            tmp.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8"); replace_retry(tmp,path)
        except Exception: pass

    def poll_once(self):
        results=[]
        for req in self.bridge.poll():
            started=time.time()
            self._active_started_at=started
            trigger=str((req.payload or {}).get("trigger") or req.kind)
            self._activity(state="RUNNING",task=req.kind,trigger=trigger,request_id=req.request_id,started_at=started)
            try:
                result=self.handle(req)
                self._session_status(result,req)
                path=self.bridge.respond(req.request_id,status=result["status"],payload=result["payload"])
                results.append((req,result,path))
            except Exception as exc:
                # A single bad/heavy checkpoint must never kill the resident bridge
                # and leave the overlay permanently stuck in RECONCILING. Surface an
                # explicit ERROR generation, answer the Lua request when possible,
                # and remain alive so the next valid snapshot can recover normally.
                detail=f"{type(exc).__name__}: {exc}"
                try:
                    set_lifecycle(
                        "ERROR", detail="Academy Engine processing failed: "+detail,
                        runtime_session=str((req.payload or {}).get("runtime_session") or ""),
                        career_uid=str((req.payload or {}).get("save_uid") or ""),
                        request_id=req.request_id, generation=0,
                    )
                except Exception:
                    pass
                result={"status":"HOLD","payload":{"accepted":False,"reason":"ENGINE_PROCESSING_ERROR","detail":detail,"request_id":req.request_id,"writes_locked":True}}
                try:
                    path=self.bridge.respond(req.request_id,status=result["status"],payload=result["payload"])
                except Exception:
                    path=None
                results.append((req,result,path))
                try:
                    err=self.bridge.root / "bridge_error.log"
                    with err.open("a",encoding="utf-8") as f:
                        f.write(f"[{time.time():.3f}] request={req.request_id} trigger={trigger} {detail}\n{traceback.format_exc()}\n")
                except Exception:
                    pass
            finally:
                self._activity(state="IDLE",task=req.kind,trigger=trigger,request_id=req.request_id,finished_at=time.time(),duration_ms=round((time.time()-started)*1000,1))
        # A health heartbeat must never take down the loop or flip the career to ERROR
        # (v1.24.09 bridge.log: WinError 5 on bridge_state.json while it was being read).
        try:
            self.bridge.publish_state(protocol=PROTOCOL_VERSION,service="READY",writes_locked=False,production_families=["PLAYSTYLE","PLAYSTYLE_PLUS","ROLE"],native_ownership=["POTENTIAL","ATTRIBUTES","AGEING"])
        except OSError:
            pass
        return results
