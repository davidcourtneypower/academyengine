from __future__ import annotations
from fc27_academy.fsutil import replace_retry
import argparse, time, builtins, os
from datetime import datetime
from pathlib import Path
from fc27_academy.file_bridge import FileBridge
from fc27_academy.bridge_service import BridgeService
from fc27_academy.receipt_ingest import ingest_receipt_files
from fc27_academy.live_playstyle_writer import apply_receipt as apply_evolution_receipt, reconcile_durable_receipts
from fc27_academy.event_engine import record_commit
from fc27_academy.save_restore_points import create_restore_point
from fc27_academy.paths import LOG_ROOT, ensure_dirs
from fc27_academy.transaction_store import lifecycle as tx_lifecycle, set_lifecycle, detach as tx_detach
from academy_manager.bridge import detect_game, live_editor_status, clear_live_session_markers
from academy_manager.overlay_export import publish_overlay_state, process_overlay_command


_LOG_FILE = None
_DEBUG_CONSOLE = False

def _rotate_log(path: Path, max_bytes: int = 5_000_000, backups: int = 3):
    try:
        if not path.exists() or path.stat().st_size < max_bytes:
            return
        oldest=path.with_name(path.name + f'.{backups}')
        oldest.unlink(missing_ok=True)
        for i in range(backups-1, 0, -1):
            src=path.with_name(path.name + f'.{i}')
            dst=path.with_name(path.name + f'.{i+1}')
            if src.exists(): replace_retry(src,dst)
        replace_retry(path, path.with_name(path.name + '.1'))
    except Exception:
        pass

_LOG_CHECK_EVERY = 200      # v1.24.38: rotate during a session too, checked every 200 lines
_log_lines = 0

def emit(*args, flush=True, **kwargs):
    # File-first logging prevents a console window from stealing focus in borderless mode.
    global _log_lines
    stamp=datetime.now().strftime('%H:%M:%S.%f')[:-3]
    msg=' '.join(str(x) for x in args)
    line=f'[{stamp}] {msg}'
    if _LOG_FILE is not None:
        _log_lines += 1
        if _log_lines % _LOG_CHECK_EVERY == 0:
            _rotate_log(_LOG_FILE)
        try:
            with _LOG_FILE.open('a', encoding='utf-8') as f:
                f.write(line+'\n')
        except Exception:
            pass
    if _DEBUG_CONSOLE:
        builtins.print(line, flush=flush, **kwargs)



def _owner_alive(pid: int) -> bool:
    if pid <= 0:
        return True
    try:
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
    except Exception:
        try:
            os.kill(pid,0); return True
        except Exception:
            return False


def _valid_uid(value) -> str:
    raw=str(value or '').strip()
    if not raw or raw.upper() in {'DEFERRED','UNKNOWN','NONE','NULL','-'}:
        return ''
    return raw

_last_runtime_marker_stamp=None

# v1.24.28: main-menu guard. FC27 sends no Career Mode event on exit to the main menu;
# Live Editor's log does show it (academy_manager.le_menu_watch). Once seen, the career
# stays detached until the Lua runtime reports something new (a career load starts with
# event 2 -> LEFT_CAREER, which changes the runtime marker).
_menu_marker_stamp=None

def _runtime_marker_mtime(bridge_root: Path):
    try: return (bridge_root/'resident_runtime_status.json').stat().st_mtime_ns
    except OSError: return None

def _main_menu_guard(bridge_root: Path, menu_seen: bool) -> bool:
    global _menu_marker_stamp
    stamp=_runtime_marker_mtime(bridge_root)
    if menu_seen:
        _menu_marker_stamp=('SEEN',stamp)
        cur=tx_lifecycle()
        emit(f"FC27AE_MAIN_MENU source=LIVE_EDITOR_LOG state={cur.get('state')} career_uid={cur.get('career_uid') or '-'} action={'DETACH' if (cur.get('career_uid') or str(cur.get('state') or '').upper() not in {'DETACHED','NO_GAME'}) else 'NONE'}", flush=True)
    if _menu_marker_stamp is None:
        return False
    if stamp!=_menu_marker_stamp[1]:
        _menu_marker_stamp=None          # the Lua runtime moved on (a career is loading)
        return False
    cur=tx_lifecycle()
    if cur.get('career_uid') or str(cur.get('state') or '').upper() not in {'DETACHED','NO_GAME'}:
        tx_detach('Returned to the FC27 main menu')
    return True

def _limits_label()->str:
    """Actual configured per-checkpoint limits (v1.24.09 logged a stale constant)."""
    try:
        from fc27_academy.runtime_config import (max_total_changes_per_checkpoint, max_normal_per_checkpoint,
            max_plus_per_checkpoint, max_role_transactions_per_checkpoint, newgen_per_checkpoint)
        return (f"{max_total_changes_per_checkpoint()}_FIELDS/{max_normal_per_checkpoint()}_NORMAL/"
                f"{max_plus_per_checkpoint()}_PLUS/{max_role_transactions_per_checkpoint()}_ROLE_TX/{newgen_per_checkpoint()}_NEWGEN")
    except Exception:
        return 'UNKNOWN'

RESPONSE_RETENTION_SECONDS=900

def _prune_responses(bridge_root: Path) -> int:
    """Delete old answered-request files; Lua only waits on the newest one (item 9)."""
    removed=0; cutoff=time.time()-RESPONSE_RETENTION_SECONDS
    for p in (bridge_root/'responses').glob('*.json'):
        try:
            if p.stat().st_mtime<cutoff: p.unlink(); removed+=1
        except OSError: pass
    return removed

def _sync_runtime_lifecycle(bridge_root: Path):
    """Translate the thin Lua adapter heartbeat into the single v1.24 lifecycle.

    The runtime marker is only evidence.  It never makes the UI READY by itself;
    READY is published atomically only after BridgeService has reconciled a full
    snapshot and overlay_export has built a complete read generation.
    """
    current=tx_lifecycle()
    if not detect_game():
        if str(current.get('state') or '').upper() not in {'NO_GAME','DETACHED'}:
            tx_detach('FC27 is not running')
        try: clear_live_session_markers()
        except Exception: pass
        return tx_lifecycle()

    try:
        marker=(live_editor_status().get('runtime_marker') or {})
    except Exception:
        marker={}
    if not marker:
        # A new FC27 process invalidates the old read generation even before the
        # Live Editor autorun has produced its first heartbeat.
        if str(current.get('state') or '').upper() not in {'CAREER_LOADING','DETACHED','NO_GAME'}:
            set_lifecycle('CAREER_LOADING', detail='Waiting for Live Editor career adapter', runtime_session='', career_uid='', storage_key='', branch_id='', request_id='', career_date={}, snapshot_sequence=0, generation=0)
        return tx_lifecycle()

    global _last_runtime_marker_stamp
    try: stamp=(str(bridge_root), (bridge_root/'resident_runtime_status.json').stat().st_mtime_ns)
    except OSError: stamp=None
    if stamp is not None and stamp==_last_runtime_marker_stamp:
        return current
    _last_runtime_marker_stamp=stamp
    mstate=str(marker.get('state') or '').upper().strip()
    session=str(marker.get('runtime_session') or '').strip()
    uid=_valid_uid(marker.get('save_uid'))
    detail=str(marker.get('detail') or '').strip()
    cstate=str(current.get('state') or '').upper()
    same_session=bool(session and session==str(current.get('runtime_session') or ''))
    same_uid=bool(uid and uid==str(current.get('career_uid') or ''))

    if mstate in {'DETACHED','NO_CAREER','LEFT_CAREER'}:
        if cstate!='DETACHED' or current.get('career_uid') or current.get('storage_key'):
            tx_detach(detail or 'Career Mode exited')
        return tx_lifecycle()

    if mstate in {'WAITING_DB','WAITING_RUNTIME_CAPABILITY'}:
        # New adapter session means the previous career cannot remain visible.
        if (session and not same_session) or cstate in {'READY','RECONCILING','ADVANCING'}:
            set_lifecycle('CAREER_LOADING', detail=detail or 'Waiting for Career Mode data', runtime_session=session, career_uid='', storage_key='', branch_id='', request_id='', career_date={}, snapshot_sequence=0, generation=0)
        return tx_lifecycle()

    if mstate in {'CAREER_SETTLING','ACTIVE_SETTLING'}:
        # If this is the same loaded career and it was previously READY, this is
        # an advance/save settle.  Preserve identity but immediately invalidate
        # the published generation so the external overlay shows PROCESSING.
        if same_session and same_uid and cstate in {'READY','ADVANCING','RECONCILING'}:
            if cstate!='ADVANCING':
                set_lifecycle('ADVANCING', detail=detail or 'Career Mode is processing', generation=0)
        else:
            # Load/switch/new runtime: never expose the old career while FC27 is
            # still settling, and never infer a UID from a DEFERRED marker.
            set_lifecycle('CAREER_LOADING', detail=detail or 'Loading Career Mode data', runtime_session=session, career_uid=uid, storage_key='', branch_id='', request_id='', career_date={}, snapshot_sequence=0, generation=0)
        return tx_lifecycle()

    if mstate=='ACTIVE':
        if not uid:
            set_lifecycle('CAREER_LOADING', detail='Waiting for loaded career identity', runtime_session=session, career_uid='', storage_key='', branch_id='', request_id='', career_date={}, snapshot_sequence=0, generation=0)
            return tx_lifecycle()
        # ACTIVE heartbeat confirms a loaded game context, not read-model readiness.
        # A new session/save must wait for its first complete CHECKPOINT_SNAPSHOT.
        if not same_session or not same_uid:
            set_lifecycle('CAREER_LOADING', detail=detail or 'Synchronizing loaded career', runtime_session=session, career_uid=uid, storage_key='', branch_id='', request_id='', career_date={}, snapshot_sequence=0, generation=0)
        # For the same context, BridgeService/overlay_export own RECONCILING/READY.
        return tx_lifecycle()

    return current

def main():
    ap=argparse.ArgumentParser(description='FC27 Academy Engine bridge (v1.24 external overlay + transactional read generations)')
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--interval', type=float, default=.20)
    ap.add_argument('--root', default=None)
    ap.add_argument('--debug', action='store_true', help='mirror detailed log output to a visible console')
    args=ap.parse_args()
    bridge=FileBridge(args.root)
    owner_pid=int(os.environ.get('FC27AE_OWNER_PID') or 0)
    global _LOG_FILE, _DEBUG_CONSOLE
    _DEBUG_CONSOLE=bool(args.debug)
    ensure_dirs(); log_dir=LOG_ROOT; log_dir.mkdir(parents=True, exist_ok=True)
    _LOG_FILE=log_dir/'bridge.log'; _rotate_log(_LOG_FILE)
    service=BridgeService(bridge)
    enable_lease=Path(bridge.root)/'engine_enabled.lease'
    from fc27_academy.engine_lease import EngineLease
    lease=EngineLease(enable_lease, lambda: not owner_pid or _owner_alive(owner_pid), log=lambda m: emit(m, flush=True))
    lease.start()
    # Live Editor Run Code truncates larger pasted scripts on some builds.
    # Stage the resident runtime in the canonical bridge root; the standalone Lua is
    # now a tiny bootstrap that dofile()s this file, avoiding the editor limit.
    runtime_src=Path(__file__).parent / "integration" / "lua" / "FC27_Academy_Engine_Runtime.lua"
    runtime_dst=Path(bridge.root)/"runtime_current.lua"
    try:
        runtime_bytes=runtime_src.read_bytes()
        tmp=runtime_dst.with_suffix(runtime_dst.suffix+'.tmp')
        tmp.write_bytes(runtime_bytes)
        replace_retry(tmp,runtime_dst)
        # Remove stale versioned aliases from earlier companion builds. The
        # autorun now targets runtime_current.lua specifically so Python/Lua
        # cannot drift onto different versioned filenames again.
        for stale in Path(bridge.root).glob('runtime_v12*.lua'):
            try: stale.unlink()
            except Exception: pass
        runtime_status=f"READY path={runtime_dst} bytes={len(runtime_bytes)} contract=runtime_current.lua"
    except Exception as exc:
        runtime_status=f"ERROR detail={exc}"
    emit(f"FC27AE_LUA_RUNTIME {runtime_status}", flush=True)
    emit(f'FC27AE_BRIDGE_SERVICE READY root={bridge.root} mode=V106_EXTERNAL_TRANSACTIONAL production=PLAYSTYLE+ROLE native=POTENTIAL+ATTRIBUTES+AGEING', flush=True)
    # Publish health immediately; the GUI should never sit in 'Starting' until the first poll cycle.
    service.bridge.publish_state(protocol=1,service='READY',version='1.0.6',writes_locked=False,production_families=['PLAYSTYLE','PLAYSTYLE_PLUS','ROLE'],native_ownership=['POTENTIAL','ATTRIBUTES','AGEING'])
    _last_overlay_publish=0.0
    _last_engine_work=time.monotonic()
    _next_history_maintenance=time.monotonic()+60
    _next_response_prune=time.monotonic()+30
    from academy_manager.le_menu_watch import MenuWatch
    menu_watch=MenuWatch()
    while True:
        if owner_pid and not _owner_alive(owner_pid):
            emit(f'FC27AE_BRIDGE_SERVICE owner launcher {owner_pid} closed; shutting down', flush=True)
            lease.close()
            break
        try:
            try: _main_menu_guard(Path(bridge.root),menu_watch.poll())
            except Exception as exc: emit(f"FC27AE_MAIN_MENU ERROR detail={exc}", flush=True)
            _life_now=_sync_runtime_lifecycle(Path(bridge.root))
            _ls=str((_life_now or {}).get('state') or '').upper()
            if _ls=='CAREER_LOADING':
                service._activity(
                    state='RUNNING', task='RUNTIME', trigger='CAREER_SETTLED_BASELINE',
                    request_id=str((_life_now or {}).get('request_id') or ''),
                    stage='Waiting for the loaded FC27 career snapshot', stage_index=0, stage_total=0,
                )
            elif _ls=='ADVANCING':
                # FC27 can announce DAY_PASSED before its development tables have
                # actually settled, and may not emit the next usable CareerModeEvent
                # until the user navigates. Show a short immediate refresh cue, then
                # keep the previous immutable generation browseable while waiting.
                # The real checkpoint request will switch activity back to RUNNING.
                age=max(0.0,time.time()-float((_life_now or {}).get('updated_at') or time.time()))
                if age < 2.25:
                    service._activity(
                        state='RUNNING', task='RUNTIME', trigger='CAREER_ADVANCE',
                        request_id=str((_life_now or {}).get('request_id') or ''),
                        stage='FC27 is advancing the career; waiting for updated player data',
                        stage_index=0, stage_total=0,
                    )
                else:
                    service._activity(
                        state='IDLE', task='RUNTIME', trigger='CAREER_ADVANCE',
                        request_id=str((_life_now or {}).get('request_id') or ''),
                        stage='Waiting for FC27 to publish the settled career snapshot',
                        stage_index=0, stage_total=0,
                    )
            # Commands are accepted only from an atomically READY generation.
            process_overlay_command()
        except Exception as exc:
            emit(f"FC27AE_RUNTIME_LIFECYCLE ERROR detail={exc}", flush=True)
        for rec in reconcile_durable_receipts(bridge.root):
            if rec.get('status')=='COMMITTED' and rec.get('storage_key'):
                try: record_commit(str(rec['storage_key']),rec)
                except Exception as exc: emit(f'FC27AE_EVENTS RECOVERY_ERROR detail={exc}',flush=True)
            emit(f'FC27AE_EVOLUTION_RECONCILE changeset={rec.get("changeset_id")} status={rec.get("status")}', flush=True)
        for receipt,dest in ingest_receipt_files(bridge.root):
            if isinstance(dest, Exception):
                emit(f'FC27AE_SYNC_RECEIPT_RX status=ERROR detail={dest}', flush=True)
            else:
                commit=apply_evolution_receipt(bridge.root,receipt)
                if commit.get('status')=='COMMITTED' and commit.get('storage_key'):
                    try:
                        sk=str(commit.get('storage_key'))
                        events=record_commit(sk,commit)
                        try: create_restore_point(sk,trigger='RECEIPT_COMMIT',request_id=str(receipt.get('changeset_id') or ''))
                        except Exception as rex: emit(f'FC27AE_RESTORE_POINT ERROR changeset={receipt.get("changeset_id")} detail={rex}', flush=True)
                        if events: emit(f'FC27AE_EVENTS created={len(events)} changeset={receipt.get("changeset_id")}', flush=True)
                    except Exception as exc:
                        emit(f'FC27AE_EVENTS ERROR changeset={receipt.get("changeset_id")} detail={exc}', flush=True)
                emit(f'FC27AE_SYNC_RECEIPT_RX changeset={receipt.get("changeset_id")} status={receipt.get("status")} reason={receipt.get("reason")} durable={dest} evolution_commit={commit.get("status") if commit.get("handled") else "N/A"}', flush=True)
        try:
            _poll_results=service.poll_once()
        except Exception as exc:
            # Last-resort guard: the resident bridge must survive a bad checkpoint.
            # BridgeService normally contains per-request failures; this protects
            # polling/IPC failures and converts them into a visible recoverable ERROR.
            emit(f'FC27AE_BRIDGE_LOOP ERROR detail={type(exc).__name__}: {exc}', flush=True)
            try: set_lifecycle('ERROR', detail=f'Academy Engine bridge error: {type(exc).__name__}: {exc}', generation=0)
            except Exception: pass
            _poll_results=[]
        if _poll_results: _last_engine_work=time.monotonic()
        for req,res,path in _poll_results:
            extra=''
            if req.kind=='CHECKPOINT_SNAPSHOT':
                b=res['payload'].get('bootstrap') or {}; pp=res['payload'].get('playstyle_plan') or {}
                extra=(f" players={res['payload'].get('player_count')} observed={b.get('observed','-')} tracked={b.get('tracked','-')} new={b.get('new','-')} returning={b.get('returning','-')} missing={b.get('missing','-')}"
                       f" club={b.get('club','-')} free_agent={b.get('free_agent','-')} other={b.get('other','-')} replaced_generation={b.get('replaced_generation','-')} generation_cohort={b.get('generation_cohort','-')} transitions={b.get('transitions','-')} role_signals={b.get('role_signals','-')} cleanup_removed={b.get('cleanup_removed_keys','-')}"
                       f" native_attr_changes={b.get('attribute_changes','-')} native_potential_changes={b.get('potential_changes','-')} playstyle_changes={b.get('playstyle_changes','-')} offline_rebase={b.get('offline_rebase',False)} elapsed_days={b.get('elapsed_days',0)} reconciled={b.get('reconciled','-')}"
                       f" ps_progress_events={b.get('playstyle_progress_events','-')} ps_progressing={pp.get('ps_progressing','-')} ps_ready={pp.get('ps_ready','-')} ps_plus_ready={pp.get('ps_plus_ready','-')} max_ps_progress={pp.get('max_ps_progress','-')} max_ps_plus={pp.get('max_ps_plus_progress','-')} trigger={req.payload.get('trigger','UNKNOWN')} snapshot_mode={req.payload.get('snapshot_mode','UNKNOWN')} coalesced_days={req.payload.get('coalesced_days',0)}")
            emit(f'FC27AE_BRIDGE_RX id={req.request_id} kind={req.kind} status={res["status"]}{extra} response={path}', flush=True)
            if req.kind=='CHECKPOINT_SNAPSHOT' and res['status']!='OK':
                br=res['payload'].get('branch_resolution') or {}
                emit(f"FC27AE_BRANCH_HOLD career_uid={res['payload'].get('save_uid')} reason={res['payload'].get('reason')} players={res['payload'].get('player_count')} candidate_seen={br.get('candidate_seen','-')} known_max={br.get('known_max','-')} trigger={req.payload.get('trigger','UNKNOWN')}", flush=True)
            if req.kind=='CHECKPOINT_SNAPSHOT' and res['status']=='OK':
                p=res['payload']; br=p.get('branch_resolution') or {}
                sc=p.get('save_context') or {}
                emit(f"FC27AE_SAVE_CONTEXT career_uid={p.get('career_uid')} branch_id={p.get('branch_id')} storage_key={p.get('storage_key')} branch_state={br.get('state')} state={sc.get('state')} parent_storage={sc.get('parent_storage_key') or '-'} identity_overlap={sc.get('identity_overlap') if sc.get('identity_overlap') is not None else '-'} trigger={req.payload.get('trigger','UNKNOWN')} boundary={req.payload.get('boundary_reason','-')} exact_lookup={(p.get('exact_save_lookup') or {}).get('status','-')}/{(p.get('exact_save_lookup') or {}).get('source','-')} exact_restore={(p.get('exact_save_anchor') or {}).get('status','-')} development_credited={(p.get('bootstrap') or {}).get('development_credited','-')} training_days={(p.get('bootstrap') or {}).get('training_days','-')}", flush=True)
                own=p.get('native_ownership') or {}
                emit(f"FC27AE_NATIVE_OWNERSHIP dynamic_potential={own.get('dynamic_potential')} attributes={own.get('attributes')} ageing={own.get('ageing')} academy_engine_writes={own.get('academy_engine_writes')}", flush=True)
                life=p.get('season_lifecycle') or {}
                emit(f"FC27AE_LIFECYCLE status={life.get('status')} season_boundary={life.get('season_boundary_signal')} cohort={life.get('generation_cohort',0)} observed={life.get('observed',0)} missing={life.get('missing',0)} club={life.get('club',0)} free_agent={life.get('free_agent',0)} other={life.get('other',0)} identity_rebases={life.get('identity_rebases_total',0)} offline_rebase={(p.get('bootstrap') or {}).get('offline_rebase',False)} invariants={','.join(life.get('invariants') or []) or 'NONE'}", flush=True)
                ga=p.get('generation_audit') or {}; ne=p.get('newgen_enrichment') or {}
                emit(f"FC27AE_NEW_COHORT checkpoint_new={ga.get('checkpoint_new',0)} ps0={ga.get('ps0',0)} ps1={ga.get('ps1',0)} ps2={ga.get('ps2',0)} ps3={ga.get('ps3',0)} ps4plus={ga.get('ps4plus',0)} with_ps_pct={ga.get('with_ps_pct',0)} with_psplus={ga.get('with_psplus',0)} with_psplus_pct={ga.get('with_psplus_pct',0)}", flush=True)
                emit(f"FC27AE_NEWGEN_ENRICH native_with_ps={ne.get('native_with_ps',0)}/{ne.get('checkpoint_new',0)} native_pct={ne.get('native_with_ps_pct',0)} proposals={ne.get('enrichment_proposals',0)} players_enriched={ne.get('players_enriched',0)} projected_with_ps={ne.get('projected_with_ps',0)} projected_pct={ne.get('projected_with_ps_pct',0)} native_hist={ne.get('native_count_hist',{})} projected_hist={ne.get('projected_count_hist',{})} mode=RICH_0_TO_5_QUEUE", flush=True)
                lt=p.get('playstyle_lifetime') or {}
                emit(f"FC27AE_PS_LIFETIME observed={lt.get('observed',0)} absolute_cap={lt.get('absolute_normal_cap',7)} cap_hist={lt.get('normal_cap_hist',{})} at_cap={lt.get('normal_at_cap',0)} plus_eligible={lt.get('plus_eligible',0)} plus_eligible_pct={lt.get('plus_eligible_pct',0)} plus_cap={lt.get('plus_cap',1)} plus_at_cap={lt.get('plus_at_cap',0)}", flush=True)
                ac=p.get('ps_acquisition') or {}; pc=p.get('ps_plus_acquisition') or {}; rc=p.get('role_acquisition') or {}; lw=p.get('live_write') or {}
                emit(f"FC27AE_PS_TRANSACTION ready_paths={ac.get('ready_paths',0)} winners={ac.get('winner_count',0)} cooldown_holds={ac.get('cooldown_holds',0)} lifetime_holds={ac.get('lifetime_cap_holds',0)} production_eligible={ac.get('production_eligible',0)}", flush=True)
                emit(f"FC27AE_PSPLUS_TRANSACTION ready_paths={pc.get('ready_paths',0)} winners={pc.get('winner_count',0)} cooldown_holds={pc.get('cooldown_holds',0)} lifetime_holds={pc.get('lifetime_eligibility_holds',0)} production_eligible={pc.get('production_eligible',0)}", flush=True)
                emit(f"FC27AE_ROLE_TRANSACTION ready_paths={rc.get('ready_paths',0)} winners={rc.get('winner_count',0)} suppressed={rc.get('suppressed_competing_paths',0)} mapping_holds={rc.get('mapping_holds',0)} cooldown_holds={rc.get('cooldown_holds',0)} production_eligible={rc.get('production_eligible',0)} cooldown_days={rc.get('cooldown_days',120)}", flush=True)
                for x in (rc.get('verified_candidates') or [])[:5]:
                    fields=','.join(f"{c.get('field')}:{c.get('expected')}->{c.get('proposed')}" for c in x.get('field_changes') or [])
                    emit(f"FC27AE_ROLE_VERIFIED pid={x.get('playerid')} role={x.get('role')} progress={x.get('progress')} fields={fields} evidence={x.get('mapping_evidence')} validation={x.get('validation')}", flush=True)
                emit(f"FC27AE_EVOLUTION_BUNDLE status={lw.get('status')} staged_fields={lw.get('staged',0)} changeset={lw.get('changeset_id','-')} kinds={lw.get('kinds',{})} role_transactions={lw.get('role_transactions',0)} queue={lw.get('queue',{})} holds={len(lw.get('holds') or [])} limits={_limits_label()}", flush=True)
                for e in lw.get('entries') or []:
                    label=e.get('role') if e.get('kind')=='ROLE_UPGRADE' else (' + '.join(e.get('styles') or []) or e.get('style'))
                    emit(f"FC27AE_EVOLUTION_STAGE kind={e.get('kind')} pid={e.get('playerid')} target={label} field={e.get('field')} expected={e.get('expected')} proposed={e.get('proposed')} evidence={e.get('mapping_evidence')}", flush=True)
                t=p.get('timings') or {}
                emit(f"FC27AE_WORKLOAD ingest_ms={t.get('ingest_ms','-')} audits_ms={t.get('audits_ms','-')} native_potential=FC27 native_attributes_ageing=FC27", flush=True)
        # Publish only after receipts and new snapshots have been processed.  The
        # publisher atomically promotes the lifecycle to READY when every section
        # (dashboard, players/progression, events/timeline, settings) belongs to
        # the same reconciled generation.
        try:
            if time.monotonic()-_last_overlay_publish >= 0.20:
                # A checkpoint that finished after the main menu appeared must not
                # bring the career back on screen.
                try: _main_menu_guard(Path(bridge.root),False)
                except Exception: pass
                _before=tx_lifecycle()
                _finalising=str((_before or {}).get('state') or '').upper()=='RECONCILING' and bool((_before or {}).get('storage_key'))
                if _finalising:
                    service._activity(state='RUNNING',task='READ_MODEL',trigger='FINALISE_READ_MODEL',request_id=str((_before or {}).get('request_id') or ''),stage='Publishing complete player, progression, event and settings data',stage_index=13,stage_total=13)
                act={}
                try:
                    ap=Path(bridge.root)/"bridge_activity.json"
                    if ap.exists():
                        import json as _json
                        act=_json.loads(ap.read_text(encoding="utf-8"))
                except Exception: pass
                _export_started=time.perf_counter()
                _published=publish_overlay_state(act)
                if _published: emit(f"FC27AE_PERF overlay_publish_ms={(time.perf_counter()-_export_started)*1000:.2f}",flush=True)
                _after=tx_lifecycle()
                if _published and str((_after or {}).get('state') or '').upper() in {'READY','DETACHED','NO_GAME','ERROR'}:
                    service._activity(state='IDLE',task='READ_MODEL',trigger='FINALISE_READ_MODEL',request_id=str((_after or {}).get('request_id') or ''),finished_at=time.time())
                _last_overlay_publish=time.monotonic()
                # v1.24.31: experimental in-game faces (off by default) mirror the loaded career.
                if str((_after or {}).get('state') or '').upper()=='READY':
                    try:
                        from academy_manager import face_sync
                        from academy_manager.live_data import active_world
                        face_sync.tick(active_world(),log=lambda m: emit(m,flush=True))
                    except Exception as exc:
                        emit(f"FC27AE_FACES ERROR {type(exc).__name__}: {exc}",flush=True)
        except Exception as exc:
            emit(f"FC27AE_OVERLAY_STATE ERROR detail={exc}", flush=True)
            try: set_lifecycle('ERROR',detail=f'Overlay read-model publication failed: {type(exc).__name__}: {exc}',generation=0)
            except Exception: pass
            try: service._activity(state='IDLE',task='READ_MODEL',trigger='FINALISE_READ_MODEL',request_id='',finished_at=time.time())
            except Exception: pass
        if time.monotonic()>=_next_history_maintenance and time.monotonic()-_last_engine_work>=60 and tx_lifecycle().get('state')=='READY':
            _next_history_maintenance=time.monotonic()+900
            try:
                from fc27_academy.path_history_store import collect_unused
                _maintenance=collect_unused()
                if _maintenance.get('status')=='COMPLETE':emit(f'FC27AE_HISTORY_MAINTENANCE removed={_maintenance["removed"]}',flush=True)
            except Exception as exc:emit(f'FC27AE_HISTORY_MAINTENANCE deferred={exc}',flush=True)
        if time.monotonic()>=_next_response_prune:
            _next_response_prune=time.monotonic()+300
            try:
                n=_prune_responses(Path(bridge.root))
                if n: emit(f'FC27AE_RESPONSE_PRUNE removed={n}',flush=True)
            except Exception as exc: emit(f'FC27AE_RESPONSE_PRUNE deferred={exc}',flush=True)
        if args.once:
            lease.close()
            break
        time.sleep(max(.05,args.interval))

if __name__=='__main__': main()
