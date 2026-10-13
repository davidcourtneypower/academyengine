-- FC27 Academy Engine v1.0.6 bootstrap
-- IMPORTANT: do not load the resident runtime during Live Editor autorun.
-- Live Editor executes lua/autorun while its own startup/injection path is still
-- finishing. Loading the DB-heavy Academy runtime here can stall that path.
-- Instead this tiny bootstrap only publishes a handshake and registers a
-- CareerModeEvent handler. The resident runtime is loaded on the first Career
-- Mode event (ENTERED_HUB_FIRST_TIME=26 on the verified FC27/LE path) and then
-- owns subsequent Career Mode events itself. The resident runtime itself has a
-- career-entry gate and performs no DB/save access during module load.

if _G.FC27AE_AUTORUN_CURRENT_LOADED then return end
_G.FC27AE_AUTORUN_CURRENT_LOADED=true

local loading=false

local function active()
 return _G.FC27AE_RUNTIME_CURRENT_STATE=="ACTIVE"
end

local function safe_log(msg)
 pcall(function()
  if type(Log)=="function" then Log(msg)
  elseif LOGGER and type(LOGGER.LogInfo)=="function" then LOGGER:LogInfo(msg)
  end
 end)
end

local function bridge_root()
 local ok,base=pcall(function()
  if type(os)=="table" and type(os.getenv)=="function" then return os.getenv("LOCALAPPDATA") end
 end)
 if ok and type(base)=="string" and base~="" then return base.."\\FC27AcademyEngine\\runtime\\bridge" end
 return nil
end

local function engine_enabled()
 local root=bridge_root(); if not root then return false end
 local f=io.open(root.."\\engine_enabled.lease","r")
 if not f then return false end
 local raw=f:read("*a"); f:close()
 local stamp=tonumber(raw or "")
 if not stamp then return false end
 return math.abs((os.time() or 0)-stamp) <= 8
end

local function esc(v)
 return tostring(v or ""):gsub("\\","\\\\"):gsub('"','\\"'):gsub("\r"," "):gsub("\n"," ")
end

local function mark(state,detail)
 local root=bridge_root(); if not root then return end
 pcall(function()
  local f=io.open(root.."\\le_bootstrap_seen.json","w")
  if not f then return end
  f:write('{"version":"1.0.6","state":"'..esc(state)..'","timestamp":'..tostring(os.time())..',"detail":"'..esc(detail)..'"}')
  f:flush(); f:close()
 end)
end

local function load_runtime(reason)
 if not engine_enabled() then return false end
 if active() then mark("RUNTIME_ACTIVE",reason); return true end
 if loading then return false end
 loading=true
 local root=bridge_root()
 if not root then
  loading=false
  mark("WAITING_FOR_RUNTIME","no_temp_root")
  safe_log("FC27AE_V106_BOOTSTRAP_WAIT reason=no_temp_root")
  return false
 end
 local runtime=root.."\\runtime_current.lua"
 mark("RUNTIME_LOAD_ATTEMPT",reason)
 local ok,err=pcall(dofile,runtime)
 loading=false
 if ok and active() then
  mark("RUNTIME_ACTIVE",reason)
  safe_log("FC27AE_V106_BOOTSTRAP_OK reason="..tostring(reason))
  return true
 end
 mark("WAITING_FOR_CAREER_RUNTIME",tostring(err or "runtime_not_ready"))
 safe_log("FC27AE_V106_BOOTSTRAP_WAIT reason="..tostring(reason).." error="..tostring(err or "runtime_not_ready"))
 return false
end

local function on_career_event(a,b,...)
 if not engine_enabled() then return end
 mark("CAREER_EVENT_SEEN","event="..tostring(b).."; runtime will settle before DB access")
 if active() then return end
 -- Keep the bootstrap inert throughout save selection and data-ready events.
 -- Day/save events allow a late engine start after the first hub event.
 if b~=26 and b~=15 and b~=28 then return end
 load_runtime("CAREER_EVENT_"..tostring(b))
end

if engine_enabled() then mark("AUTORUN_ACTIVE","REGISTERING_CAREER_HANDLER") end

if type(AddEventHandler)=="function" then
 local ok,err=pcall(AddEventHandler,"post__CareerModeEvent",on_career_event)
 if ok then
  if engine_enabled() then
   mark("AUTORUN_ARMED","post__CareerModeEvent")
   safe_log("FC27AE_V106_AUTORUN_ARMED runtime=runtime_current.lua trigger=post__CareerModeEvent")
  end
 else
  if engine_enabled() then
   mark("AUTORUN_ERROR","AddEventHandler:"..tostring(err))
   safe_log("FC27AE_V106_AUTORUN_ERROR AddEventHandler="..tostring(err))
  end
 end
else
 if engine_enabled() then
  mark("AUTORUN_ERROR","AddEventHandler unavailable")
  safe_log("FC27AE_V106_AUTORUN_ERROR AddEventHandler_unavailable")
 end
end
