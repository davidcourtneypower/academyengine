"""v1.24.17-20: the base name pool is Huffman-compressed (v1.24.16 dumps: header+0x38 points
at a blob = 552-byte tree, then [char count][bits] strings at the logged offsets 552,
559, 569, 578). Builds such a blob in a simulated memory image, in each of the four
undocumented variants (bit order x child order) and both length conventions (characters,
as the v1.24.17 log implies: 26/30 strings validated when counting bytes, failures being
accented names; or bytes), and checks the runtime finds the right
variant by validation only, resolves every name by id, and refuses a corrupted pool."""
import heapq, itertools
from pathlib import Path
from lupa import LuaRuntime
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "integration/lua/FC27_Academy_Engine_Runtime.lua").read_text(encoding="utf-8")
start = src.index("local function fix_count(t)"); end = src.index("local function get_table(name)")
cache_src = src[src.index("-- Base player names"):src.index("local function team_name(tid)")]
NAMES = ["Aaron", "Abdoulaye", "Adama", "Bruno", "Carlos", "Dario", "Emre", "Fábio", "Gaël", "Hugo", "Ivan", "Jonas",
         "Kai", "Luca", "Mats", "Nico", "O'Brien", "Pérez", "Quentin", "Rúben", "Sami", "Tiago", "Ugo", "Vito",
         "Wout", "Xavi", "Yann", "Zé", "Van Dijk", "De Bruyne", "Ødegaard", "Müller", "Ståle", "Łukasz", "Çağlar"]
HEADER, FIRST, RS = 0x20000000, 0x10000000, 12

def build_tree(texts):
    freq = {}
    for t in texts:
        for b in t.encode("utf-8"):
            freq[b] = freq.get(b, 0) + 1
    cnt = itertools.count()
    heap = [(f, next(cnt), ("leaf", b)) for b, f in freq.items()]
    heapq.heapify(heap)
    while len(heap) > 1:
        f1, _, a = heapq.heappop(heap); f2, _, b = heapq.heappop(heap)
        heapq.heappush(heap, (f1 + f2, next(cnt), ("node", a, b)))
    root = heap[0][2]
    nodes, queue = [], [root]
    index = {id(root): 0}
    while queue:                     # breadth-first, root = 0
        n = queue.pop(0); nodes.append(n)
        for c in n[1:]:
            if c[0] == "node":
                index[id(c)] = len(nodes) + len(queue); queue.append(c)
    codes = {}
    def walk(n, path):
        if n[0] == "leaf": codes[n[1]] = path; return
        walk(n[1], path + "0"); walk(n[2], path + "1")
    walk(root, "")
    return nodes, index, codes

def child_bytes(c, index):
    return bytes([0, c[1]]) if c[0] == "leaf" else bytes([index[id(c)] & 0xFF, index[id(c)] >> 8])

def make_blob(texts, msb, swap, corrupt=False, count_chars=True):
    nodes, index, codes = build_tree(texts)
    tree = b""
    for n in nodes:
        a, b = child_bytes(n[1], index), child_bytes(n[2], index)
        tree += (b + a) if swap else (a + b)
    strings, offsets = b"", []
    for t in texts:
        raw = t.encode("utf-8")
        bits = "".join(codes[x] for x in raw)
        on_boundary = len(bits) % 8 == 0
        bits += "0" * (-len(bits) % 8)
        data = bytearray()
        for i in range(0, len(bits), 8):
            chunk = bits[i:i + 8]
            data.append(int(chunk, 2) if msb else int(chunk[::-1], 2))
        if on_boundary: data.append(0)    # real encoder: extra empty byte on a byte boundary (v1.24.18 log)
        if corrupt: data = bytes((x ^ 0x5A) for x in data)
        offsets.append(len(tree) + len(strings))
        strings += bytes([len(t) if count_chars else len(raw)]) + bytes(data)
    return tree + strings, offsets

def run(msb, swap, corrupt=False, count_chars=True):
    blob, offsets = make_blob(NAMES, msb, swap, corrupt, count_chars)
    lua = LuaRuntime(unpack_returned_tuples=True, encoding=None)
    lua.execute(r'''
mem={}
function ReadBytes(a,n) local t={} for i=0,n-1 do t[i+1]=mem[a+i] or 0 end return t end
package.preload['imports/core/memory']=function() return {
  ReadQword=function(_,a) return 0x10000000 end, ReadInt=function(_,a) return 12 end,
  ReadShort=function(_,a) return ROWS end, ReadChar=function(_,a) return 0 end,
  ReadBytes=function(_,a,n) return ReadBytes(a,n) end } end
package.preload['imports/core/logger']=function() return {LogInfo=function() end,LogDebug=function() end} end
package.preload['imports/t3db/field']=function() return {new=function() return {} end} end
MEMORY={ReadBytes=function(_,a,n) return ReadBytes(a,n) end}
''')
    g = lua.globals(); g.ROWS = len(NAMES) + 1
    TABLE = lua.execute((ROOT / "tests/le_reference/t3db_table_v27_1_0.lua").read_text(encoding="utf-8"))
    g.TABLE = TABLE
    mem = g.mem
    blob_addr = FIRST + RS * (len(NAMES) + 1) + 0x18
    for i, b in enumerate(blob): mem[blob_addr + i] = b
    for i, b in enumerate(blob_addr.to_bytes(8, "little")): mem[HEADER + 0x38 + i] = b
    for r in range(len(NAMES) + 1):
        base = FIRST + r * RS
        o = 0xFFFFFFFF if r == 0 else offsets[r - 1]
        for k, b in enumerate(o.to_bytes(4, "little")): mem[base + k] = b
        mem[base + 4] = r & 0xFF; mem[base + 5] = r >> 8
    lua.execute(r'''
function make_names()
 local t=TABLE:new(); t:Load(1, {shortname_name_tables_map=setmetatable({}, {__index=function() return "playernames" end}), field_desc_map={}})
 t.fields={nameid={type=3,offset=4,startbit=0,sz=16,fld_desc={depth=16,min=0}}, name={type=13,offset=0,startbit=0,sz=608,fld_desc={depth=608,min=0}}}
 t.GetRecordFieldValue=function(self,rec,f) local idx=(rec-self.first_record)//self.record_size if f=="nameid" then return idx end return nil end
 return t
end
static_names={}; dynamic_names={}; edited_names={}; logs={}
safe_log=function(m) logs[#logs+1]=m end
clean_name=function(v) return tostring(v or "") end
le={db={GetTable=function(_,n) if n=="playernames" then return make_names() end return nil end,
  GetDBFromService=function() return 1 end, GetTableFromDB=function(_,d) return 0x20000000 end,
  GetNextTable=function() return 0 end, GetNextDB=function() return 0 end,
  GetT3DBTableName=function(_,t) return "playernames" end}}
''')
    lua.execute(src[start:end] + "\nlocal function get_table(name) return fix_count(le.db:GetTable(name)) end\n" + cache_src
                + "\n_G.build_name_cache=build_name_cache\nfunction resolve(id) return dynamic_names[id] or static_names[id] or static_lookup(id) or '' end")
    lua.eval("build_name_cache")()
    return lua, "\n".join((x.decode("utf-8","replace") if isinstance(x,bytes) else str(x)) for x in lua.eval("logs").values())

# The confirmed FC27 format (high-bit first, first child = bit 0, byte count, extra empty
# byte on a byte boundary) resolves every name; other layouts are rejected, not guessed.
lua, text = run(True, False, count_chars=False)
assert "FC27AE_STATIC_NAMES_POOL found source=HEADER_PTR+0x38 validated=" in text, text[-1500:]
got = [lua.eval(f"resolve({i})").decode("utf-8") for i in range(1, len(NAMES) + 1)]
assert got == NAMES, list(zip(got, NAMES))
assert lua.eval("resolve(0)") == b""
for msb, swap in ((False, False), (True, True), (False, True)):
    lua, text = run(msb, swap, count_chars=False)
    assert "FC27AE_STATIC_NAMES_POOL not_found" in text and lua.eval("resolve(3)") == b"", (msb, swap, text[-600:])
print(f"Huffman pool (confirmed FC27 layout): {len(NAMES)} names incl. UTF-8 accents resolve by id; other bit/child layouts rejected: PASS")

lua, text = run(True, False, corrupt=True)
assert "FC27AE_STATIC_NAMES_POOL not_found" in text and lua.eval("resolve(3)") == b"", text[-800:]
print("Corrupted pool: rejected, no names guessed: PASS")

# Real strings from the v1.24.18 Live Editor log: the decoded examples and failures prove
# MSB order with a byte count; "A. Alaadin" / "A. Amorim" end exactly on a byte boundary and
# carry one extra byte, which v1.24.19 accepts.
src_rule = src[src.index("local fits="):src.index("\n", src.index("local fits="))]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute("function fits(bits,gap) " + src_rule + " return fits end")
for bits, gap, ok in ((48, 8, True), (48, 7, True), (64, 9, True), (72, 10, True), (50, 8, True), (41, 7, True), (40, 7, True), (32, 7, False), (49, 7, False)):
    assert bool(lua.eval(f"fits({bits},{gap})")) == ok, (bits, gap)
print("Byte-boundary rule: logged real cases (48 bits/gap 8, 64/9, 72/10) accepted; mismatches rejected: PASS")
