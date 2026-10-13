"""v1.24.12 regression: base playernames dictionary (>32,767 rows) is fully read.

Uses Live Editor 27.1.0's own t3db table.lua (copied to tests/le_reference) with mocked
memory reporting the signed record count seen in the real log (playernames=-22470).
"""
from pathlib import Path
from lupa import LuaRuntime
ROOT = Path(__file__).resolve().parents[1]
ROWS = 65536 - 22470          # 43,066
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
package.preload['imports/core/memory']=function() return {
  ReadQword=function(_,a) return 1000000 end, ReadInt=function(_,a) return 16 end,
  ReadShort=function(_,a) return -22470 end, ReadChar=function(_,a) return 0 end,
  ReadBytes=function(_,a,n) local t={} for i=1,(n or 1) do t[i]=65 end t[1]=(n==1) and 0 or 65 return t end } end
package.preload['imports/core/logger']=function() return {LogInfo=function() end,LogDebug=function() end} end
package.preload['imports/t3db/field']=function() return {new=function() return {} end} end
''')
TABLE = lua.execute((ROOT / "tests/le_reference/t3db_table_v27_1_0.lua").read_text(encoding="utf-8"))
lua.globals().TABLE = TABLE
lua.execute(r'''
function make_names()
 local t=TABLE:new(); t:Load(1, {shortname_name_tables_map=setmetatable({}, {__index=function() return "playernames" end}), field_desc_map={}})
 t.GetRecordFieldValue=function(self,rec,f)
  local idx=(rec-self.first_record)//self.record_size
  if f=="nameid" then return idx end
  return "Name"..idx
 end
 return t
end
function count_rows(t)
 local n=0; local r=t:GetFirstRecord()
 while r and r~=0 do n=n+1; r=t:GetNextValidRecord() end
 return n
end
''')
raw = lua.eval("make_names()")
assert raw.written_records == -22470 and lua.eval("count_rows")(raw) <= 1, "LE iteration with signed count should visit ~nothing"

# The runtime's own fix_count/build_name_cache, extracted from the shipped Lua.
src = (ROOT / "integration/lua/FC27_Academy_Engine_Runtime.lua").read_text(encoding="utf-8")
start = src.index("local function fix_count(t)"); end = src.index("local function get_table(name)")
lua.execute(src[start:end] + "\n_G.fix_count=fix_count")
fixed = lua.eval("fix_count")(lua.eval("make_names()"))
assert fixed.written_records == ROWS
visited = lua.eval("count_rows")(fixed)
assert visited >= ROWS - 1, visited     # LE's iterator skips only its final index
print(f"Names: LE 27.1.0 iterator visits {lua.eval('count_rows')(raw)} row(s) with the signed count; after fix_count {visited:,} of {ROWS:,}: PASS")

# Full runtime path: build_name_cache resolves generated players from the base dictionary.
cache_src = src[src.index("-- Base player names"):src.index("local function team_name(tid)")]
lua.execute(r'''
static_names={}; dynamic_names={}; edited_names={}; logs={}
safe_log=function(m) logs[#logs+1]=m end
clean_name=function(v) return tostring(v or "") end
le={db={GetTable=function(_,n) if n=="playernames" then return make_names() end return nil end}}
''')
lua.execute(src[start:end] + "\nlocal function get_table(name) return fix_count(le.db:GetTable(name)) end\n" + cache_src + "\n_G.build_name_cache=build_name_cache")
lua.eval("build_name_cache")()
assert lua.eval("static_names[34045]") == "Name34045" and lua.eval("static_names[5371]") == "Name5371"
logs = lua.eval("logs"); text = " ".join(str(logs[i]) for i in range(1, len(logs) + 1))
assert "FC27AE_STATIC_NAMES loaded=43065" in text or "FC27AE_STATIC_NAMES loaded=43066" in text, text
print("Names: runtime builds a plain-text base dictionary over the corrected count (ids 34045/5371 resolve): PASS")
