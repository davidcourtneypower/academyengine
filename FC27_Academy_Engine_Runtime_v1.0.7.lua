-- FC27 Academy Engine v1.0.7 - thin Live Editor game adapter
-- Checkpoint capture remains read-only. A receipt-gated atomic evolution bundle may contain verified PlayStyle and Role writes.
-- DAY_PASSED=15 consumes any ready transaction and emits/coalesces a live checkpoint snapshot.
-- PREPARE_FOR_SAVE=28 is a durable reconciliation fallback; manual saves are not required for ordinary daily progression.
-- Stable process-wide singleton contract. The autorun must never infer readiness
-- from a release-specific token. A repeated dofile during the same FC27 process
-- returns immediately instead of registering another CareerModeEvent handler.
if _G.FC27AE_RUNTIME_CURRENT_STATE=="ACTIVE" then
 if type(Log)=="function" then pcall(Log,"FC27AE_V107_RUNTIME_REUSE state=ACTIVE") end
 return
end
-- A previous top-level load that aborted can leave LOADING behind. Career events
-- are synchronous, so LOADING here is stale rather than a legitimate concurrent load.
if _G.FC27AE_RUNTIME_CURRENT_STATE=="LOADING" then _G.FC27AE_RUNTIME_CURRENT_STATE=nil end
_G.FC27AE_RUNTIME_CURRENT_STATE="LOADING"
local le=LE
local root=(os.getenv("LOCALAPPDATA") or ".").."\\FC27AcademyEngine\\runtime\\bridge"
-- Returns enabled, reason, age_seconds. Reason/age feed the v1.24.13 lapse log.
local function engine_enabled()
 local f=io.open(root.."\\engine_enabled.lease","r")
 if not f then return false,"MISSING",-1 end
 local raw=f:read("*a"); f:close()
 local stamp=tonumber(raw or "")
 if not stamp then return false,"UNREADABLE",-1 end
 local age=(os.time() or 0)-stamp
 if math.abs(age) <= 8 then return true,"OK",age end
 return false,"STALE",age
end
if not engine_enabled() then _G.FC27AE_RUNTIME_CURRENT_STATE=nil; return end
-- Bridge root is created by the companion app before Live Editor starts.
-- Avoid spawning a shell during Live Editor autorun/startup.
local RUNTIME_STATUS=root.."\\resident_runtime_status.json"
local SESSION=""
local active_save_uid=nil
local function runtime_status(state,detail,uid)
 local f=io.open(RUNTIME_STATUS,"w")
 if not f then return end
 local d=tostring(detail or ""):gsub("\\","\\\\"):gsub('"','\\"'):gsub("\r"," "):gsub("\n"," ")
 -- IMPORTANT: never call GetSaveUID from the module-load path. Loading a save can
 -- dispatch the first CareerModeEvent while FC27 is still mutating career tables.
 -- The UID is populated only after the startup-settle gate has completed.
 local suid=tostring(uid or active_save_uid or "DEFERRED")
 f:write('{"version":"1.0.7","state":"'..tostring(state)..'","timestamp":'..tostring(os.time())..',"runtime_session":"'..tostring(SESSION or "")..'","save_uid":"'..suid..'","detail":"'..d..'"}')
 f:flush();f:close()
end
local function safe_log(msg)
 pcall(function()
  if type(Log)=="function" then Log(msg)
  elseif LOGGER and type(LOGGER.LogInfo)=="function" then LOGGER:LogInfo(msg)
  end
 end)
end
local leagues,ltl,tpl,players,teams
-- v1.24.13 crash forensics: around loads and exits every CareerModeEvent is logged, and
-- a NATIVE line is written *before* any call into FC27/Live Editor, so the last line of a
-- crashed session's log shows exactly what Academy Engine did. v1.24.38: no longer opened
-- by every save, and two minutes instead of five.
local TRACE_SECONDS=120
local trace_until=0
local lease_lapsed_at=nil; local lease_skipped=0
local function trace_window(seconds) trace_until=math.max(trace_until,(os.time() or 0)+(seconds or 300)) end
local function tracing() return (os.time() or 0)<=trace_until end
local function trace(b,phase) if tracing() then safe_log("FC27AE_EVENT ev="..tostring(b).." phase="..tostring(phase)) end end
-- v1.24.12: Live Editor 27.1.0 reads a table's record count with ReadShort (signed
-- 16-bit). Tables with more than 32,767 rows - "playernames" has ~43,000 - get a
-- negative count, so GetNextValidRecord stops immediately and almost no rows are
-- visited. That is why generated players showed "Generated Player #id". Correct the
-- count to its unsigned value before iterating any table.
local function fix_count(t)
 if t and type(t.written_records)=="number" and t.written_records<0 then
  t.written_records=t.written_records+65536
  t.last_record_idx=t.written_records-1
 end
 return t
end
local function get_table(name) return fix_count(le.db:GetTable(name)) end
local function refresh_tables()
 le=LE
 if not le or not le.db then return false,"no_db" end
 leagues=get_table("leagues"); ltl=get_table("leagueteamlinks")
 tpl=get_table("teamplayerlinks"); players=get_table("players"); teams=get_table("teams")
 if not leagues or not ltl or not tpl or not players then return false,"missing_table" end
 return true,"OK"
end
local helpers_ready=false
local REQUEST_FILES=root.."\\request_files"; local RESPONSES=root.."\\responses"
local BATCH=48; SESSION=tostring(os.time()).."_"..tostring(math.floor((os.clock() or 0)*1000000)); local SPECIAL={[2028]=true}; local FREE_AGENT_LEAGUE=382; local dirty=false; local day_epoch=0; local seq=0; local inflight_id=nil; local coalesced_days=0; local save_day_epochs={}; local stabilize_events=0; local consume_armed=false
local generated_cache={}; local cache_valid=false; local force_full_scan=true; local last_full_scan_day=-999; local FULL_SCAN_INTERVAL_DAYS=7; local pending_day_snapshot=false
-- Await a trusted in-career event; menu event counts never unlock native access.
local startup_settle_events=0; local pending_initial_snapshot=false; local awaiting_load=true
-- v1.24.12: a boundary inside an already-baselined career is a re-sync, not a load.
local baselined_uid={}; local boundary_reason="INITIAL"; local boundary_count=0; local detached_logged=false; local detached_uid=nil
local save_parent=nil; local save_parent_at=0; local inflight_since=0; local last_wait_log=0
local active_ctx={career_uid="",branch_id="",storage_key="",runtime_session="",writes_held=true,reason="NO_CONTEXT"}
local RUNTIME_TOKEN="v107_"..SESSION
_G.FC27AE_ACTIVE_RUNTIME_TOKEN=RUNTIME_TOKEN
_G.FC27AE_ACTIVE_SYNC_CONSUMER_TOKEN=RUNTIME_TOKEN
local function is_active_runtime() return _G.FC27AE_ACTIVE_RUNTIME_TOKEN==RUNTIME_TOKEN and _G.FC27AE_ACTIVE_SYNC_CONSUMER_TOKEN==RUNTIME_TOKEN end
local function safe_uid(v) return (tostring(v or "UNKNOWN"):gsub("[^%w%-%_]","_")) end
local function current_uid() return (type(GetSaveUID)=="function" and tostring(GetSaveUID())) or "UNKNOWN" end
local function refresh_active_context()
 local p=root.."\\active_context.lua"; local ok,ctx=pcall(dofile,p)
 if ok and type(ctx)=="table" and tostring(ctx.career_uid or "")==current_uid() and tostring(ctx.runtime_session or "")==tostring(SESSION) then active_ctx=ctx; return true end
 active_ctx={career_uid=current_uid(),branch_id="",storage_key="",runtime_session="",writes_held=true,reason="CONTEXT_OR_SESSION_UNAVAILABLE"}; return false
end
local function save_root()
 local key=tostring(active_ctx.storage_key or "")
 if key=="" then key=current_uid() end
 return root.."\\saves\\"..safe_uid(key)
end
local function pending_path() return save_root().."\\pending_sync.lua" end
local function receipts_path() return save_root().."\\lua_receipts" end
local OUTF={"crossing","finishing","headingaccuracy","shortpassing","volleys","defensiveawareness","standingtackle","slidingtackle","dribbling","curve","freekickaccuracy","longpassing","ballcontrol","shotpower","jumping","stamina","strength","longshots","acceleration","sprintspeed","agility","reactions","balance","aggression","composure","interceptions","positioning","vision","penalties"}
local GK={"gkdiving","gkhandling","gkkicking","gkpositioning","gkreflexes"}
local EX={"overallrating","potential","preferredposition1","preferredposition2","preferredposition3","preferredposition4","preferredposition5","nationality","birthdate","firstnameid","lastnameid","commonnameid","playerjerseynameid","trait1","trait2","icontrait1","icontrait2","role1","role2","role3","role4","role5"}
local function mkdir() return true end
local function write_branch_hint(parent_uid,child_uid,parent_ctx)
 if not parent_uid or not child_uid or parent_uid==child_uid or child_uid=="UNKNOWN" then return end
 local ctx=parent_ctx or active_ctx
 if tostring(ctx.career_uid or "")~=tostring(parent_uid) or tostring(ctx.storage_key or "")=="" then return end
 local d=root.."\\branch_hints"
 local p=d.."\\"..safe_uid(child_uid)..".json"; local f=io.open(p,"w")
 if f then f:write('{"parent_save_uid":"'..tostring(parent_uid)..'","child_save_uid":"'..tostring(child_uid)..'","parent_branch_id":"'..tostring(ctx.branch_id or "")..'","parent_storage_key":"'..tostring(ctx.storage_key or "")..'","runtime_session":"'..SESSION..'"}'); f:flush(); f:close() end
end
local function num(v) if type(v)=="number" then return tostring(math.floor(v)) end return "null" end
local function jstr(v)
 v=tostring(v or "")
 v=v:gsub("\\","\\\\"):gsub('"','\\"'):gsub("\r","\\r"):gsub("\n","\\n")
 return '"'..v..'"'
end
local edited_names={}; local dynamic_names={}; local static_names={}; local team_name_cache={}; local user_team_id=0
local name_first_failure=nil
local function clean_name(v)
 local s=tostring(v or ""):gsub("^%s+",""):gsub("%s+$",""):gsub("%s+"," ")
 return s
end
-- Base player names (playernames, ~43k rows). The name field is t3db type 13, which
-- Live Editor's Lua table API cannot read: each 12-byte record holds a 32-bit offset into a
-- Huffman-compressed pool. The table header (+0x38) points at the pool, which starts with
-- the tree (4-byte nodes: two 16-bit children; a child with low byte 0 is a leaf whose high
-- byte is the character, otherwise it is the next node index; root = node 0, first child =
-- bit 0, bits read high to low). Each name is [byte count][bits]; when the bits end exactly
-- on a byte boundary the game stores one extra empty byte. Format confirmed on FC27 data
-- (v1.24.16-v1.24.19 diagnostics); validated again every session before any name is used.
local static_names_loaded=false; local static_names_attempted=false
local static_name_offsets={}; local static_name_pool=nil
local function mem_bytes(addr,n)
 if type(MEMORY)~="table" or type(addr)~="number" or addr<=0 then return nil end
 local ok,b=pcall(function() return MEMORY:ReadBytes(addr,n) end)
 if ok and type(b)=="table" then return b end
 return nil
end
local function mem_u32(addr)
 local b=mem_bytes(addr,4); if not b then return nil end
 return (b[1] or 0)+(b[2] or 0)*256+(b[3] or 0)*65536+(b[4] or 0)*16777216
end
local function mem_u64(addr)
 local b=mem_bytes(addr,8); if not b then return nil end
 local v=0; for i=8,1,-1 do v=v*256+(b[i] or 0) end; return v
end
local function huff_load(base,tree_bytes)
 if tree_bytes<8 or tree_bytes>4096 or tree_bytes%4~=0 then return nil end
 local b=mem_bytes(base,tree_bytes); if not b then return nil end
 local nodes={}
 for i=0,tree_bytes//4-1 do nodes[i]={b[i*4+1],b[i*4+2],b[i*4+3],b[i*4+4]} end
 return nodes
end
local function huff_decode(nodes,data,first,nbytes)
 local out={}; local node=0; local bitpos=0; local total=(#data-first+1)*8
 while #out<nbytes do
  if bitpos>=total then return nil,bitpos,table.concat(out) end
  local byte=data[first+(bitpos//8)] or 0
  local bit=(byte>>(7-bitpos%8))&1
  bitpos=bitpos+1
  local n=nodes[node]; if not n then return nil end
  local lo,hi
  if bit==0 then lo,hi=n[1],n[2] else lo,hi=n[3],n[4] end
  if lo==0 then
   if hi==0 then return nil end
   out[#out+1]=string.char(hi); node=0
  else
   node=lo+hi*256; if not nodes[node] then return nil end
  end
 end
 return table.concat(out),bitpos
end
local function huff_text_ok(t)
 if not t or t=="" then return false end
 for i=1,#t do local c=t:byte(i); if c<32 or c==127 then return false end end
 return true
end
local function validate_pool(base,sorted)
 local nodes=huff_load(base,sorted[1]); if not nodes then return 0,0 end
 local good,tested,examples,failures=0,0,{},{}
 for i=1,math.min(#sorted-1,30) do
  local off,nxt=sorted[i],sorted[i+1]; local gap=nxt-off
  if gap>=2 and gap<=80 then
   tested=tested+1
   local d=mem_bytes(base+off,gap)
   if d then
    local txt,bits,partial=huff_decode(nodes,d,2,d[1] or 0)
    local fits=bits and ((((bits+7)//8)==gap-1) or (bits%8==0 and bits//8==gap-2))
    if txt and huff_text_ok(txt) and fits then good=good+1; if #examples<5 then examples[#examples+1]=txt end
    elseif #failures<3 then failures[#failures+1]="off="..off.." gap="..gap.." count="..tostring(d[1]).." bits="..tostring(bits) end
   end
  end
 end
 return good,tested,nodes,examples,failures
end
local function locate_name_pool(st,header)
 local offs={}; local seen={}
 for _,o in pairs(static_name_offsets) do if not seen[o] then seen[o]=true; offs[#offs+1]=o end end
 table.sort(offs)
 if #offs<10 then return nil,"too_few_offsets" end
 local cands={}
 if header then local q=mem_u64(header+0x38); if q and q>0 then cands[#cands+1]={"HEADER_PTR+0x38",q} end end
 local endrec=(tonumber(st.first_record) or 0)+(tonumber(st.record_size) or 0)*(tonumber(st.written_records) or 0)
 cands[#cands+1]={"END_OF_RECORDS+0x18",endrec+0x18}
 local report={}
 for _,c in ipairs(cands) do
  local good,tested,nodes,examples,failures=validate_pool(c[2],offs)
  report[#report+1]=c[1].."="..good.."/"..tested..((failures and #failures>0) and (" ["..table.concat(failures,"; ").."]") or "")
  if tested>=8 and good>=tested-1 then return {base=c[2],nodes=nodes,examples=examples,source=c[1],good=good,tested=tested},table.concat(report,",") end
 end
 return nil,table.concat(report,",")
end
local function static_lookup(id)
 if not static_name_pool then return nil end
 local off=static_name_offsets[id]; if not off then return nil end
 local d=mem_bytes(static_name_pool.base+off,81)
 local txt=d and huff_decode(static_name_pool.nodes,d,2,d[1] or 0)
 if not huff_text_ok(txt) then return nil end
 txt=clean_name(txt)
 if txt~="" then static_names[id]=txt; return txt end
 return nil
end
local function playernames_header()
 local db=le and le.db
 if not db or type(db.GetDBFromService)~="function" then return nil end
 local ok,h=pcall(function()
  local d=db:GetDBFromService()
  while d and d>0 do
   local t=db:GetTableFromDB(d)
   while t and t>0 do
    if db:GetT3DBTableName(t)=="playernames" then return t end
    t=db:GetNextTable(t)
   end
   d=db:GetNextDB(d)
  end
  return nil
 end)
 if ok then return h end
 return nil
end
local function build_name_cache()
 -- User-edited / promoted players (editedplayernames) and the dynamic dictionary.
 local ok,t=pcall(function() return get_table("editedplayernames") end)
 if ok and t then
  local r=t:GetFirstRecord()
  while r and r~=0 do
   local pid=t:GetRecordFieldValue(r,"playerid")
   if type(pid)=="number" and pid>=460000 then
    local first=clean_name(t:GetRecordFieldValue(r,"firstname")); local sur=clean_name(t:GetRecordFieldValue(r,"surname")); local common=clean_name(t:GetRecordFieldValue(r,"commonname"))
    local name=clean_name(first.." "..sur); if name=="" then name=common end
    if name~="" then edited_names[pid]=name end
   end
   r=t:GetNextValidRecord()
  end
 end
 local dok,dt=pcall(function() return get_table("dcplayernames") end)
 if dok and dt then
  local r=dt:GetFirstRecord()
  while r and r~=0 do
   local nid=dt:GetRecordFieldValue(r,"nameid"); local nv=clean_name(dt:GetRecordFieldValue(r,"name"))
   if type(nid)=="number" and nv~="" then dynamic_names[nid]=nv end
   r=dt:GetNextValidRecord()
  end
 end
 -- The base dictionary is static for the game session: index it once.
 if static_names_loaded or static_names_attempted then return end
 local sok,st=pcall(function() return get_table("playernames") end)
 if not (sok and st) then return end
 static_names_attempted=true
 local name_field=st.fields and st.fields["name"]
 local name_type=name_field and name_field.type
 local n,offsets=0,0
 local rok,rerr=pcall(function()
  local r=st:GetFirstRecord()
  while r and r~=0 do
   local nid=st:GetRecordFieldValue(r,"nameid")
   if type(nid)=="number" then
    if name_type==13 then
     local off=mem_u32(r+(tonumber(name_field.offset) or 0))
     if off and off~=0xFFFFFFFF then static_name_offsets[nid]=off; offsets=offsets+1 end
    else
     local nv=clean_name(st:GetRecordFieldValue(r,"name")); if nv~="" then static_names[nid]=nv; n=n+1 end
    end
   end
   r=st:GetNextValidRecord()
  end
 end)
 if name_type==13 and offsets>0 then
  local pool,report=locate_name_pool(st,playernames_header())
  if pool then
   static_name_pool=pool; n=offsets
   safe_log("FC27AE_STATIC_NAMES_POOL found source="..pool.source.." validated="..pool.good.."/"..pool.tested.." offsets="..offsets.." examples="..table.concat(pool.examples or {},"|"))
  else
   safe_log("FC27AE_STATIC_NAMES_POOL not_found offsets="..offsets.." tried="..tostring(report))
  end
 end
 static_names_loaded=(n>0)
 safe_log("FC27AE_STATIC_NAMES loaded="..tostring(n).." rows="..tostring(st.written_records).." ok="..tostring(rok).." name_type="..tostring(name_type)..(rok and "" or (" error="..tostring(rerr))))
end
local function team_name(tid)
 tid=tonumber(tid or 0) or 0
 if tid<=0 then return "" end
 local cached=team_name_cache[tid]
 if cached and cached~="" then return cached end
 local name=""
 if type(GetTeamName)=="function" then local ok,v=pcall(GetTeamName,tid); if ok and type(v)=="string" then name=clean_name(v) end end
 -- FC27 LE's localization helper can return empty while localization is still
 -- initializing. The teams table itself carries teamname and is a reliable fallback.
 if name=="" and teams then
  local r=teams:GetFirstRecord()
  while r and r~=0 do
   if tonumber(teams:GetRecordFieldValue(r,"teamid"))==tid then
    name=clean_name(teams:GetRecordFieldValue(r,"teamname")); break
   end
   r=teams:GetNextValidRecord()
  end
 end
 if name~="" then team_name_cache[tid]=name end
 return name
end
local function player_name(pid,vals,tid)
 local name=edited_names[pid]
 if name and name~="" then return name end
 vals=vals or {}
 local function by_id(v)
  local id=tonumber(v or -1) or -1
  return dynamic_names[id] or static_names[id] or static_lookup(id) or ""
 end
 local common=by_id(vals.commonnameid)
 local first=by_id(vals.firstnameid)
 local sur=by_id(vals.lastnameid)
 local jersey=by_id(vals.playerjerseynameid)
 name=clean_name(first.." "..sur); if name=="" then name=clean_name(common) end; if name=="" then name=clean_name(jersey) end
 if name~="" then edited_names[pid]=name; return name end
 if not name_first_failure then
  name_first_failure={pid=pid,firstnameid=vals.firstnameid,lastnameid=vals.lastnameid,commonnameid=vals.commonnameid,playerjerseynameid=vals.playerjerseynameid}
 end
 return "Generated Player #"..tostring(pid)
end
local clubteam={}; local teamleague={}
local function build_club_teams()
 clubteam={}; teamleague={}
 local kind={}
 for s=0,(tonumber(leagues.written_records) or 0)-1,BATCH do local e=math.min(s+BATCH-1,(tonumber(leagues.written_records) or 0)-1); for i=s,e do
  local r=leagues.first_record+leagues.record_size*i; if leagues:IsRecordValid(r) then local lid=leagues:GetRecordFieldValue(r,"leagueid"); local intl=leagues:GetRecordFieldValue(r,"isinternationalleague"); local women=leagues:GetRecordFieldValue(r,"iswomencompetition"); if lid==FREE_AGENT_LEAGUE then kind[lid]="F" elseif SPECIAL[lid] then kind[lid]="S" elseif women~=0 then kind[lid]="W" elseif intl~=0 then kind[lid]="I" else kind[lid]="C" end end
 end end
 for s=0,(tonumber(ltl.written_records) or 0)-1,BATCH do local e=math.min(s+BATCH-1,(tonumber(ltl.written_records) or 0)-1); for i=s,e do
  local r=ltl.first_record+ltl.record_size*i; if ltl:IsRecordValid(r) then local lid=ltl:GetRecordFieldValue(r,"leagueid"); local k=kind[lid]; if k=="C" or k=="F" then local tid=ltl:GetRecordFieldValue(r,"teamid"); if tid~=112264 then clubteam[tid]=(k=="F") and "FREE_AGENT" or "CLUB"; teamleague[tid]=lid end end end
 end end
 -- Prime the team-name cache directly from the DB once per full discovery. This
 -- avoids thousands of localization calls and still lets GetTeamName override it.
 if teams then
  local r=teams:GetFirstRecord()
  while r and r~=0 do
   local tid=teams:GetRecordFieldValue(r,"teamid"); local tn=clean_name(teams:GetRecordFieldValue(r,"teamname"))
   if type(tid)=="number" and tn~="" then team_name_cache[tid]=tn end
   r=teams:GetNextValidRecord()
  end
 end
end
local function active_generated()
 local active={}
 for s=0,(tonumber(tpl.written_records) or 0)-1,BATCH do local e=math.min(s+BATCH-1,(tonumber(tpl.written_records) or 0)-1); for i=s,e do
  local r=tpl.first_record+tpl.record_size*i; if tpl:IsRecordValid(r) then local pid=tpl:GetRecordFieldValue(r,"playerid"); if pid and pid>=460000 then local tid=tpl:GetRecordFieldValue(r,"teamid"); if clubteam[tid] then active[pid]={teamid=tid,lifecycle=clubteam[tid],tpl_rec=r} end end end
 end end
 return active
end
local function player_json(pid,link,r,current_date)
 local tid=link.teamid; local lifecycle=link.lifecycle
 local vals={}; for _,f in ipairs(EX) do vals[f]=players:GetRecordFieldValue(r,f) end
 do local okg,gv=pcall(function() return players:GetRecordFieldValue(r,"gender") end); vals.gender=okg and gv or nil end
 local pname=player_name(pid,vals,tid); local cname=team_name(tid)
 local pos=vals.preferredposition1; local fields=(pos==0) and GK or OUTF; local attrs={}
 for _,f in ipairs(fields) do local v=players:GetRecordFieldValue(r,f); if v==nil then return nil end; attrs[#attrs+1]='"'..f..'":'..num(v) end
 local roles={}; for i=1,5 do roles[#roles+1]=num(vals["role"..i]) end
 local positions={}; for i=1,5 do positions[#positions+1]=num(vals["preferredposition"..i]) end
 local bd=DATE:new(); bd:FromGregorianDays(vals.birthdate); local age=CalculatePlayerAge(current_date,bd)
 return '{"playerid":'..num(pid)..',"name":'..jstr(pname)..',"clubteamid":'..num(tid)..',"clubname":'..jstr(cname)..',"leagueid":'..num(teamleague[tid])..',"is_user_team":'..((tonumber(tid)==tonumber(user_team_id)) and 'true' or 'false')..',"lifecycle":"'..lifecycle..'","preferredposition1":'..num(pos)..',"positions":['..table.concat(positions,",")..'],"overallrating":'..num(vals.overallrating)..',"potential":'..num(vals.potential)..',"gender":'..num(vals.gender)..',"nationality":'..num(vals.nationality)..',"birthdate":'..num(vals.birthdate)..',"firstnameid":'..num(vals.firstnameid)..',"lastnameid":'..num(vals.lastnameid)..',"commonnameid":'..num(vals.commonnameid)..',"playerjerseynameid":'..num(vals.playerjerseynameid)..',"dob":{"day":'..num(bd.day)..',"month":'..num(bd.month)..',"year":'..num(bd.year)..'},"age":'..num(age)..',"trait1":'..num(vals.trait1)..',"trait2":'..num(vals.trait2)..',"icontrait1":'..num(vals.icontrait1)..',"icontrait2":'..num(vals.icontrait2)..',"role1":'..num(vals.role1)..',"role2":'..num(vals.role2)..',"role3":'..num(vals.role3)..',"role4":'..num(vals.role4)..',"role5":'..num(vals.role5)..',"roles":['..table.concat(roles,",")..'],"attributes":{'..table.concat(attrs,",")..'}}' 
end
local function emit_snapshot(trigger)
 local rok,rerr=refresh_tables(); if not rok then return false,"DB_NOT_READY:"..tostring(rerr),0,0,0,"NONE" end
 local current_date=GetCurrentDate()
 user_team_id=0
 if type(GetUserTeamID)=="function" then local ok,v=pcall(GetUserTeamID); if ok and type(v)=="number" then user_team_id=v end end
 local user_team_name=team_name(user_team_id)
 local season_start=(tonumber(current_date.month or 1)>=7) and tonumber(current_date.year or 0) or (tonumber(current_date.year or 0)-1)
 local season_label=(season_start>0) and (tostring(season_start).."/"..string.format("%02d",(season_start+1)%100)) or ""
 local do_full=force_full_scan or (not cache_valid) or trigger=="CAREER_SETTLED_BASELINE" or trigger=="SCREEN_LOADED_BASELINE" or trigger=="BOUNDARY_RESYNC" or trigger=="SAVE_STABILIZED" or trigger=="PREPARE_FOR_SAVE" or ((day_epoch-last_full_scan_day)>=FULL_SCAN_INTERVAL_DAYS)
 local mode=do_full and "FULL_DISCOVERY" or "CACHED_TRACKED"
 name_first_failure=nil
 local active=nil
 if do_full then build_club_teams(); build_name_cache(); active=active_generated() end

 local found=0; local incomplete=0; local stale_cache=0
 seq=seq+1; local cid=string.format("session:%s:save:%d:day:%d",SESSION,seq,day_epoch); local rid=string.format("fc27_evo_v12106_%s_%d_%d",SESSION,seq,day_epoch)
 local saveuid=(type(GetSaveUID)=="function" and GetSaveUID()) or "UNKNOWN"
 mkdir()
 local final=REQUEST_FILES.."\\"..rid..".request.json"; local tmp=final..".tmp"
 local f=io.open(tmp,"w"); if not f then return false,"open_failed",0,0,0,mode end
 local bytes=0
 local function put(x) f:write(x); bytes=bytes+#x end
 local new_cache={}
 local ok,err=pcall(function()
  put('{"protocol":1,"request_id":"'..rid..'","kind":"CHECKPOINT_SNAPSHOT","payload":{"checkpoint_id":"'..cid..'","save_uid":"'..tostring(saveuid)..'","runtime_session":"'..SESSION..'","day_epoch":'..day_epoch..',"checkpoint_seq":'..seq..',"trigger":"'..tostring(trigger or "UNKNOWN")..'","coalesced_days":'..coalesced_days..',"boundary_reason":"'..tostring(boundary_reason)..'","boundary_count":'..boundary_count..',"snapshot_mode":"'..mode..'","writes_locked":false,"career":{"user_teamid":'..num(user_team_id)..',"team_name":'..jstr(user_team_name)..',"date":{"day":'..num(current_date.day)..',"month":'..num(current_date.month)..',"year":'..num(current_date.year)..'},"season":'..jstr(season_label)..'},"players":[')
  local first=true
  if do_full then
   for s=0,(tonumber(players.written_records) or 0)-1,BATCH do local e=math.min(s+BATCH-1,(tonumber(players.written_records) or 0)-1); for i=s,e do
    local pr=players.first_record+players.record_size*i
    if players:IsRecordValid(pr) then
     local pid=players:GetRecordFieldValue(pr,"playerid"); local link=active[pid]
     if link then
      local j=player_json(pid,link,pr,current_date)
      if j then
       if not first then put(',') end; put(j); first=false; found=found+1
       new_cache[pid]={player_rec=pr,tpl_rec=link.tpl_rec}
      else incomplete=incomplete+1 end
      active[pid]=nil
     end
    end
   end end
  else
   local ids={}; for pid,_ in pairs(generated_cache) do ids[#ids+1]=pid end; table.sort(ids)
   for _,pid in ipairs(ids) do
    local c=generated_cache[pid]; local pr=c.player_rec; local tr=c.tpl_rec
    local good=pr and tr and players:IsRecordValid(pr) and tpl:IsRecordValid(tr)
    if good and players:GetRecordFieldValue(pr,"playerid")==pid and tpl:GetRecordFieldValue(tr,"playerid")==pid then
     local tid=tpl:GetRecordFieldValue(tr,"teamid"); local lc=clubteam[tid]
     if lc then
      local j=player_json(pid,{teamid=tid,lifecycle=lc},pr,current_date)
      if j then if not first then put(',') end; put(j); first=false; found=found+1; new_cache[pid]=c else incomplete=incomplete+1 end
     else
      stale_cache=stale_cache+1
     end
    else
     stale_cache=stale_cache+1
    end
   end
  end
  put(']}}')
  f:flush(); f:close()
 end)
 if not ok then pcall(function() f:close() end); pcall(os.remove,tmp); force_full_scan=true; return false,tostring(err),found,incomplete,bytes,mode end
 pcall(os.remove,final)
 local renamed,rerr2=os.rename(tmp,final)
 if not renamed then pcall(os.remove,tmp); force_full_scan=true; return false,"rename_failed:"..tostring(rerr2),found,incomplete,bytes,mode end
 if do_full then
  generated_cache=new_cache; cache_valid=true; force_full_scan=false; last_full_scan_day=day_epoch
 else
  generated_cache=new_cache
  local previous=found+stale_cache
  if stale_cache>math.max(8,math.floor(previous*0.02)) then force_full_scan=true end
 end
 inflight_id=rid; inflight_since=os.time(); coalesced_days=0
 if mode=="FULL_DISCOVERY" then
  local resolved=0; for _,v in pairs(edited_names) do if v and v~="" then resolved=resolved+1 end end
  safe_log("FC27AE_METADATA team_id="..tostring(user_team_id).." team_name="..tostring(user_team_name or "").." players="..tostring(found).." named="..tostring(math.min(resolved,found)).." base_names="..(static_name_pool and "HUFFMAN" or (static_names_loaded and "TEXT" or "UNAVAILABLE")))
 end
 if name_first_failure then local nf=name_first_failure; safe_log("FC27AE_NAME_UNRESOLVED_SAMPLE pid="..tostring(nf.pid).." firstnameid="..tostring(nf.firstnameid).." lastnameid="..tostring(nf.lastnameid).." commonnameid="..tostring(nf.commonnameid).." jerseynameid="..tostring(nf.playerjerseynameid)) end
 return true,rid,found,incomplete,bytes,mode
end
local function mkdir_receipts() return true end
local function receipt(cid,status,reason)
 reason=tostring(reason or "OK")
 safe_log("FC27AE_UNIFIED_SYNC_RECEIPT changeset="..tostring(cid).." status="..status.." reason="..reason)
 mkdir_receipts()
 local final=receipts_path().."\\"..tostring(cid)..".receipt.json"; local tmp=final..".tmp"
 local f=io.open(tmp,"w")
 if f then f:write('{"changeset_id":"'..tostring(cid)..'","status":"'..status..'","reason":"'..reason..'"}'); f:flush(); f:close(); pcall(os.remove,final); pcall(os.rename,tmp,final) end
end
local function consume()
 refresh_active_context()
 if active_ctx.writes_held then safe_log("FC27AE_UNIFIED_SYNC HOLD reason=BRANCH_CONTEXT_HELD:"..tostring(active_ctx.reason)); return false end
 local PENDING=pending_path(); local probe=io.open(PENDING,"r"); if not probe then return false end; probe:close()
 local ok,tx=pcall(dofile,PENDING)
 if not ok or type(tx)~="table" or (tx.schema~=1 and tx.schema~=2) or type(tx.changes)~="table" or #tx.changes==0 then
  safe_log("FC27AE_UNIFIED_SYNC HOLD reason=INVALID_PENDING"); return false
 end
 local cid=tostring(tx.changeset_id or "UNKNOWN")
 if tx.schema>=2 and tostring(tx.runtime_session or "")~=tostring(SESSION) then receipt(cid,"REJECTED","RUNTIME_SESSION_MISMATCH"); pcall(os.remove,PENDING); return true end
 if type(GetSaveUID)~="function" then receipt(cid,"REJECTED","NO_SAVE_UID"); pcall(os.remove,PENDING); return true end
 if tostring(GetSaveUID())~=tostring(tx.career_uid or tx.save_uid) then receipt(cid,"REJECTED","CAREER_UID_MISMATCH"); pcall(os.remove,PENDING); return true end
 if tostring(active_ctx.branch_id or "")~=tostring(tx.branch_id or "") or tostring(active_ctx.storage_key or "")~=tostring(tx.storage_key or tx.save_uid) then receipt(cid,"REJECTED","BRANCH_CONTEXT_MISMATCH"); pcall(os.remove,PENDING); return true end
 local players=LE and LE.db and fix_count(LE.db:GetTable("players")); if not players then receipt(cid,"REJECTED","NO_PLAYERS_TABLE"); return false end
 local wanted={}; for _,c in ipairs(tx.changes) do if type(c.pid)~="number" or c.pid<460000 then receipt(cid,"REJECTED","PLAYER_GUARD"); pcall(os.remove,PENDING); return true end; wanted[c.pid]=true end
 for _,g in ipairs(tx.branch_guards or {}) do if type(g.pid)=="number" then wanted[g.pid]=true end end
 local recs={}; local r=players:GetFirstRecord()
 while r and r~=0 do local pid=players:GetRecordFieldValue(r,"playerid"); if wanted[pid] then recs[pid]=r end; r=players:GetNextValidRecord() end
 for _,g in ipairs(tx.branch_guards or {}) do
  local gr=recs[g.pid]; if not gr then receipt(cid,"STALE","BRANCH_GUARD_PLAYER_MISSING:"..tostring(g.pid)); pcall(os.remove,PENDING); return true end
  if players:GetRecordFieldValue(gr,"birthdate")~=g.birthdate or players:GetRecordFieldValue(gr,"nationality")~=g.nationality then receipt(cid,"STALE","BRANCH_GUARD_MISMATCH:"..tostring(g.pid)); pcall(os.remove,PENDING); return true end
 end
 for _,c in ipairs(tx.changes) do
  if not recs[c.pid] then receipt(cid,"STALE","PLAYER_NOT_FOUND:"..tostring(c.pid)); pcall(os.remove,PENDING); return true end
  local live=players:GetRecordFieldValue(recs[c.pid],c.field); if live~=c.expected then receipt(cid,"STALE","EXPECTED_"..c.pid.."_"..c.field.."_LIVE_"..tostring(live)); pcall(os.remove,PENDING); return true end
 end
 local applied={}
 safe_log("FC27AE_WRITE_BEGIN changeset="..tostring(cid).." fields="..tostring(#tx.changes))
 for _,c in ipairs(tx.changes) do
  players:SetRecordFieldValue(recs[c.pid],c.field,c.target)
  if players:GetRecordFieldValue(recs[c.pid],c.field)~=c.target then
   for i=#applied,1,-1 do local a=applied[i]; players:SetRecordFieldValue(recs[a.pid],a.field,a.expected) end
   receipt(cid,"ROLLED_BACK","READBACK:"..c.pid..":"..c.field); pcall(os.remove,PENDING); return true
  end
  applied[#applied+1]=c
 end
 for _,c in ipairs(tx.changes) do if players:GetRecordFieldValue(recs[c.pid],c.field)~=c.target then
  for i=#applied,1,-1 do local a=applied[i]; players:SetRecordFieldValue(recs[a.pid],a.field,a.expected) end
  receipt(cid,"ROLLED_BACK","FINAL_VERIFY"); pcall(os.remove,PENDING); return true
 end end
 if tx.restore_after_success then
  for i=#applied,1,-1 do local a=applied[i]; players:SetRecordFieldValue(recs[a.pid],a.field,a.expected) end
  for _,c in ipairs(tx.changes) do if players:GetRecordFieldValue(recs[c.pid],c.field)~=c.expected then receipt(cid,"ROLLED_BACK","TEST_RESTORE_VERIFY"); pcall(os.remove,PENDING); return true end end
  receipt(cid,"APPLIED","TEST_RESTORED")
 else
  receipt(cid,"APPLIED","COMMITTED")
 end
 pcall(os.remove,PENDING); return true
end

local function response_complete()
 if not inflight_id then return true end
 local p=RESPONSES.."\\"..tostring(inflight_id)..".json"
 local f=io.open(p,"r")
 if f then
  f:close(); inflight_id=nil; refresh_active_context(); consume_armed=not active_ctx.writes_held
  if active_ctx.writes_held then safe_log("FC27AE_BRANCH_CONTEXT HOLD reason="..tostring(active_ctx.reason)) else safe_log("FC27AE_BRANCH_CONTEXT READY branch="..tostring(active_ctx.branch_id).." storage="..tostring(active_ctx.storage_key)) end
  return true
 end
 if os.time()-inflight_since>=30 and os.time()-last_wait_log>=30 then
  last_wait_log=os.time(); safe_log("FC27AE_RESPONSE_WAIT request="..tostring(inflight_id).." age="..tostring(os.time()-inflight_since))
 end
 return false
end

local function consume_ready()
 if inflight_id or not consume_armed or awaiting_load or pending_initial_snapshot or stabilize_events>0 then return end
 local ok,handled=pcall(consume)
 if not ok then safe_log("FC27AE_UNIFIED_SYNC HOLD reason=CONSUMER_ERROR:"..tostring(handled)); return end
 -- Keep an unconsumed handoff armed; a missing file is not a successful write.
 if handled then consume_armed=false; dirty=true end
end

local function try_snapshot(trigger)
 if not response_complete() then
  coalesced_days=coalesced_days+1
  safe_log("FC27AE_REALTIME COALESCE trigger="..tostring(trigger).." inflight="..tostring(inflight_id).." day_epoch="..tostring(day_epoch).." coalesced="..tostring(coalesced_days))
  return false
 end
 consume_ready()
 local t=os.clock(); local ok,id,found,incomplete,bytes,mode=emit_snapshot(trigger); local ms=math.floor((os.clock()-t)*1000+0.5)
 if ok then dirty=false; safe_log(string.format("FC27AE_REALTIME SENT trigger=%s mode=%s id=%s players=%d incomplete=%d bytes=%d elapsed_ms=%d",tostring(trigger),tostring(mode),id,found,incomplete,bytes,ms))
 else safe_log(string.format("FC27AE_REALTIME FAIL trigger=%s mode=%s reason=%s players=%d incomplete=%d elapsed_ms=%d dirty_retained=1",tostring(trigger),tostring(mode),tostring(id),found or -1,incomplete or -1,ms)) end
 return ok
end

-- v1.24.12 event policy (IDs from Live Editor 27.1.0 career_mode/enums.lua).
-- Native game/DB access is allowed only on settled in-career events. Every other
-- event returns before any native call. v1.24.09/10 resolved a "save switch" on
-- any event and ran a full DB scan while FC27 was tearing the career down after
-- Quit (event 2 TOURNAMENT_MODE_ACTIVATED -> 146 -> scan with players=0 -> crash).
local SETTLED_EVENTS={[12]=true,[13]=true,[15]=true,[16]=true,[17]=true,[18]=true,[19]=true,[26]=true,[27]=true,[28]=true,[53]=true,[68]=true,[147]=true}
-- Menu / career-creation / teardown signals: quarantine without touching the game.
local EXIT_EVENTS={[2]=true,[3]=true,[4]=true,[6]=true,[30]=true}
local function quarantine(reason,detail)
 if active_save_uid then detached_uid=active_save_uid end
 active_save_uid=nil; awaiting_load=true; consume_armed=false; inflight_id=nil
 pending_initial_snapshot=false; pending_day_snapshot=false; stabilize_events=0
 cache_valid=false; force_full_scan=true; generated_cache={}; save_parent=nil
 leagues=nil; ltl=nil; tpl=nil; players=nil; teams=nil
 trace_window(TRACE_SECONDS)
 runtime_status("LEFT_CAREER",detail,"DEFERRED")
 safe_log("FC27AE_CAREER_EXIT reason="..tostring(reason).." day_epoch="..tostring(day_epoch).." native_access=HELD")
end
local function OnCareerEvent(a,b,...)
 if not is_active_runtime() then return end
 if awaiting_load then trace(b,"RECEIVED_AWAITING_LOAD") else trace(b,"RECEIVED") end
 -- Load boundaries must be processed without calling any native game API. They are
 -- handled even while the bridge lease is lapsed so the runtime never keeps treating
 -- a different (or reloaded) career as the active one.
 if b==5 or b==29 then
  trace_window(TRACE_SECONDS)
  boundary_count=boundary_count+1; boundary_reason="EVENT_"..tostring(b)
  safe_log("FC27AE_LOAD_BOUNDARY event="..tostring(b).." day_epoch="..tostring(day_epoch).." inflight="..tostring(inflight_id or "-").." pending_day="..tostring(pending_day_snapshot).." count="..tostring(boundary_count))
  awaiting_load=true; consume_armed=false; inflight_id=nil; pending_initial_snapshot=true
  cache_valid=false; force_full_scan=true; pending_day_snapshot=false; dirty=true; save_parent=nil
  leagues=nil; ltl=nil; tpl=nil; players=nil; teams=nil
  runtime_status("CAREER_SETTLING","Waiting for career hub before accessing game data","DEFERRED")
  return
 end
 if EXIT_EVENTS[b] then
  if not awaiting_load or active_save_uid then quarantine("EVENT_"..tostring(b),"Career Mode exited; game data access held") end
  return
 end
 local lease_ok,lease_reason,lease_age=engine_enabled()
 if not lease_ok then
  -- The bridge is not running (launcher closed or engine stopped). Nothing touches
  -- the game, but days still count so elapsed-day evidence stays correct when the
  -- bridge comes back. There is no idle/same-day timeout anywhere in the engine.
  if not lease_lapsed_at then
   lease_lapsed_at=os.time(); lease_skipped=0
   safe_log("FC27AE_LEASE_LAPSED reason="..tostring(lease_reason).." age="..tostring(lease_age).." event="..tostring(b).." day_epoch="..tostring(day_epoch))
  end
  lease_skipped=lease_skipped+1
  if b==15 and active_save_uid and not awaiting_load then
   day_epoch=day_epoch+1; save_day_epochs[active_save_uid]=day_epoch; pending_day_snapshot=true; dirty=true
  end
  return
 end
 if lease_lapsed_at then
  safe_log("FC27AE_LEASE_RESTORED lapsed_s="..tostring(os.time()-lease_lapsed_at).." events_while_lapsed="..tostring(lease_skipped).." event="..tostring(b).." day_epoch="..tostring(day_epoch))
  lease_lapsed_at=nil; lease_skipped=0
 end
 -- Unsettled events (matches, sims, news, transfers, ...) never touch native APIs.
 if not SETTLED_EVENTS[b] then return end
 -- DATA_READY (27) and SCREEN_HAS_DONE_LOADING (68) also occur during menu/load
 -- flows. Neither an arbitrary event count nor those events proves a loaded career.
 -- Late/manual attachment can use a subsequent day or save event instead of hub 26.
 local career_entry=(b==26 or b==15 or b==28)
 if awaiting_load and not career_entry then return end
 -- v1.24.13: SCREEN_HAS_DONE_LOADING (68) and DATA_READY (27) also fire on menus
 -- and while FC27 is loading another save; the 08-10 crash log shows Academy Engine's
 -- last game calls happening on such a 68. Touch the game on them only when a day
 -- capture is actually waiting. Pending writes are applied on the next day/save event.
 if (b==68 or b==27) and not pending_day_snapshot and not pending_initial_snapshot and stabilize_events==0 then
  -- (response_complete is not called here either: it resolves the save UID.)
  trace(b,"NO_NATIVE_ACCESS")
  return
 end
 trace(b,"NATIVE IsInCM+GetSaveUID")
 if type(IsInCM)~="function" then
  runtime_status("WAITING_RUNTIME_CAPABILITY","IsInCM unavailable; game data access held","DEFERRED")
  return
 end
 local ok,in_cm=pcall(IsInCM)
 if not ok or not in_cm then
  -- Day events still arrive while the career context is unavailable; keep counting
  -- them for the save we detached from so cooldown/elapsed-day evidence stays true.
  if active_save_uid then detached_uid=active_save_uid end
  if b==15 and detached_uid then day_epoch=day_epoch+1; save_day_epochs[detached_uid]=day_epoch end
  if not detached_logged then
   detached_logged=true; boundary_count=boundary_count+1; boundary_reason="DETACH_EVENT_"..tostring(b)
   safe_log("FC27AE_DETACH event="..tostring(b).." in_cm_ok="..tostring(ok).." day_epoch="..tostring(day_epoch).." inflight="..tostring(inflight_id or "-").." count="..tostring(boundary_count))
  end
  active_save_uid=nil; generated_cache={}; cache_valid=false; force_full_scan=true
  pending_initial_snapshot=false; pending_day_snapshot=false; awaiting_load=true
  consume_armed=false; inflight_id=nil; save_parent=nil
  leagues=nil; ltl=nil; tpl=nil; players=nil; teams=nil
  runtime_status("DETACHED","Career context unavailable; game data access held","DEFERRED")
  return
 end
 if detached_logged then detached_logged=false; safe_log("FC27AE_REATTACH event="..tostring(b).." day_epoch="..tostring(day_epoch)) end
 if not helpers_ready then
  local loaded,err=pcall(function()
   require 'imports/career_mode/helpers'
   require 'imports/other/helpers'
  end)
  if not loaded then runtime_status("WAITING_RUNTIME_CAPABILITY","Career helpers unavailable: "..tostring(err),"DEFERRED"); return end
  helpers_ready=true
 end
 local ready_event=career_entry or (not awaiting_load and (b==27 or b==68))
 if awaiting_load then pending_initial_snapshot=true end
 startup_settle_events=0
 local uid=current_uid()
 local day_counted=false
 -- A save-UID change outside a trusted hub/day/save event is FC27 leaving the
 -- career (or loading another one). Never resolve it here: hold all DB access
 -- until the next trusted event, which runs the normal load/switch baseline.
 if active_save_uid and active_save_uid~=uid and not career_entry then
  quarantine("SAVE_UID_CHANGED_EVENT_"..tostring(b),"Career Mode exited or switching save; game data access held")
  return
 end
 runtime_status("ACTIVE","CareerModeEvent:"..tostring(b),uid)
 if active_save_uid~=uid then
  runtime_status("ACTIVE_SETTLING","Save switch detected; waiting for FC27 career tables to settle",uid)
  if active_save_uid then save_day_epochs[active_save_uid]=day_epoch end
  local previous=active_save_uid
  local parent=(save_parent and os.time()-save_parent_at<=120) and save_parent or nil
  if previous and (b==28 or parent) and not awaiting_load then
   write_branch_hint(previous,uid,parent or active_ctx)
  end
  consume_armed=false
  active_save_uid=uid; day_epoch=save_day_epochs[uid] or 0; inflight_id=nil; coalesced_days=0; dirty=true; stabilize_events=ready_event and 0 or 2; generated_cache={}; cache_valid=false; force_full_scan=true; pending_day_snapshot=false
  if b==15 then day_epoch=day_epoch+1; save_day_epochs[uid]=day_epoch; day_counted=true end
  -- Re-attaching to the same save after a detach is a boundary re-sync, not a switch.
  if previous==nil and detached_uid==uid and baselined_uid[uid] then boundary_reason="DETACH_RESUME" else boundary_reason="SAVE_SWITCH" end
  detached_uid=nil
  trace_window(TRACE_SECONDS)
  safe_log("FC27AE_SAVE_SWITCH old="..tostring(previous or "-").." new="..tostring(uid).." day_epoch="..tostring(day_epoch).." event="..tostring(b).." settle=2 writes=HELD")
  pending_initial_snapshot=true
  if not ready_event then return end
 end
 if stabilize_events>0 and ready_event then stabilize_events=0; pending_initial_snapshot=true end
 if stabilize_events>0 then
  runtime_status("ACTIVE_SETTLING","Career data settling; remaining="..tostring(stabilize_events),uid)
  if b==15 then dirty=true; day_epoch=day_epoch+1; save_day_epochs[uid]=day_epoch; day_counted=true end
  if b==28 then dirty=true end
  stabilize_events=stabilize_events-1
  safe_log("FC27AE_SAVE_STABILIZE uid="..tostring(uid).." remaining="..tostring(stabilize_events).." event="..tostring(b).." writes=HELD")
  if stabilize_events==0 then pending_initial_snapshot=true end
  return
 end
 response_complete()
 if b==28 and not awaiting_load then
  refresh_active_context()
  if not active_ctx.writes_held then
   save_parent={career_uid=active_ctx.career_uid,branch_id=active_ctx.branch_id,storage_key=active_ctx.storage_key}
   save_parent_at=os.time()
  end
 end
 if pending_initial_snapshot and not inflight_id and (ready_event or (b~=15 and b~=28)) then
  -- A day that passes across a boundary still happened; count it so Python's
  -- elapsed-day evidence and cooldowns stay correct (v1.24.09 silently dropped it).
  if b==15 and not day_counted then day_epoch=day_epoch+1; save_day_epochs[uid]=day_epoch; day_counted=true end
  local trigger="SAVE_STABILIZED"
  if awaiting_load then
   -- First snapshot of this save in this runtime session is a genuine load baseline.
   -- Later boundaries (event 5/29 or a transient IsInCM=false) are re-syncs; Python
   -- decides from branch continuity and elapsed-day evidence whether growth counts.
   trigger=(baselined_uid[uid] and boundary_reason~="SAVE_SWITCH") and "BOUNDARY_RESYNC" or "SCREEN_LOADED_BASELINE"
  end
  pending_initial_snapshot=false; awaiting_load=false; dirty=true
  if not try_snapshot(trigger) then pending_initial_snapshot=true; awaiting_load=true
  else baselined_uid[uid]=true end
  return
 end
 if awaiting_load or pending_initial_snapshot then return end
 consume_ready()
 if b==15 then
  -- If no intermediate event followed the prior day, capture it now before
  -- replacing its pending marker. This also services acknowledged award writes.
  if pending_day_snapshot and not inflight_id then
   if try_snapshot("DAY_SETTLED") then pending_day_snapshot=false end
  end
  runtime_status("ACTIVE_SETTLING","Career advancing; waiting for FC27 development tables to settle",uid)
  dirty=true; day_epoch=day_epoch+1; save_day_epochs[uid]=day_epoch
  if pending_day_snapshot or inflight_id then coalesced_days=coalesced_days+1 end
  pending_day_snapshot=true
  safe_log(string.format("FC27AE_EVOLUTION DAY_PASSED day_epoch=%d capture=DEFERRED_TO_SETTLED_EVENT coalesced=%d",day_epoch,coalesced_days))
  return
 elseif b==28 then
  if try_snapshot("PREPARE_FOR_SAVE") then pending_day_snapshot=false end
  return
 end
 -- Growth/new-player events request a refreshed snapshot on the next settled event.
 -- DAY_PASSED fires before FC27 has always committed all development-table updates.
 -- Capture on the next ordinary Career Mode event instead of blocking the game thread
 -- with a large synchronous scan. Rapid calendar simulation naturally coalesces here.
 if pending_day_snapshot and not inflight_id then
  if try_snapshot("DAY_SETTLED") then pending_day_snapshot=false end
 end
end
if type(AddEventHandler)~="function" or type(io)~="table" or type(io.open)~="function" then
 _G.FC27AE_ACTIVE_RUNTIME_TOKEN=nil; _G.FC27AE_ACTIVE_SYNC_CONSUMER_TOKEN=nil; _G.FC27AE_RUNTIME_CURRENT_STATE=nil
 runtime_status("WAITING_RUNTIME_CAPABILITY","AddEventHandler/io unavailable")
 safe_log("FC27AE_AUTO_SNAPSHOT_WAIT reason=runtime_capability"); return
end
AddEventHandler("post__CareerModeEvent",OnCareerEvent)
_G.FC27AE_RUNTIME_CURRENT_STATE="ACTIVE"
runtime_status("ACTIVE_SETTLING","resident_ready_no_db_touch","DEFERRED")
safe_log("FC27AE_UNIFIED_V107_READY session="..SESSION.." token="..RUNTIME_TOKEN.." startup=NO_NATIVE_ACCESS_UNTIL_CAREER_HUB events=DAY_PASSED:15_DEFERRED_SETTLED,PREPARE_FOR_SAVE:28_RECONCILE batch=48 adapter=SNAPSHOT_PLUS_RECEIPT_GATED_WRITES production_sync=RECEIPT_GATED storage=APP_PERSISTENT_BRANCH_STATE save_switch=UID_PLUS_STATE_FINGERPRINT transport=STREAMED_ATOMIC_FILE realtime=HYBRID_DEFERRED_CACHED_TRACKED full_scan_days=7 native_growth=FC27")
-- No GetSaveUID, table access, player scan or snapshot is allowed at module load.
-- The first baseline is scheduled only after later CareerModeEvents have settled.
