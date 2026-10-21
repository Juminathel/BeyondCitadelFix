# Which LoadGameFromSlot calls are reachable from an event (e.g. ReceiveTick) through the
# ubergraph, custom-event stubs and called functions.
# usage: python3 reach.py <base> [Event ...]
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disasm import Ctx, fmt
from ustruct import parse_struct
import kismet

class BP:
    def __init__(self, base):
        self.c = c = Ctx(base); u = open(base + '.uexp', 'rb').read(); H = c.p.total_header
        self.funcs, self.entry, self.uber = {}, {}, None
        for i, e in enumerate(c.ex):
            if e['cls'] != 'Function': continue
            s = parse_struct(c.p, u[e['off'] - H:e['off'] - H + e['size']])
            st, _ = kismet.parse_script(s['script'])
            self.funcs[e['name']] = st
            if e['name'].startswith('ExecuteUbergraph'): self.uber = e['name']
        for name, st in self.funcs.items():
            for x in st:
                if x[0] == 0x46 and c.ref(x[1]).endswith(self.uber or '\0') and x[2] and x[2][0][0] == 0x1D:
                    self.entry[name] = x[2][0][1]
        if self.uber:
            us = self.funcs[self.uber]
            self.idx = {x.m: i for i, x in enumerate(us)}

    def callee_names(self, stmt):
        out = []
        for n in kismet.walk(stmt):
            if n[0] in (0x46, 0x1C, 0x68): out.append(self.c.ref(n[1]).split('.')[-1])
            elif n[0] in (0x45, 0x1B): out.append(self.c.p.nm(*n[1]))
        return out

    def reach(self, event):
        """Returns (set of (function, stmt offset) with LoadGameFromSlot, set of visited events)."""
        loads, seen_f = set(), set()
        def visit_func(name):
            if name in seen_f: return
            seen_f.add(name)
            if name in self.entry: return visit_uber(self.entry[name], name)
            if name not in self.funcs or name == self.uber: return
            for x in self.funcs[name]: stmt(name, x)
        def stmt(fn, x):
            for cn in self.callee_names(x):
                if cn == 'LoadGameFromSlot': loads.add((fn, x.m))
                elif cn in self.funcs: visit_func(cn)
        def visit_uber(start, label):
            us = self.funcs[self.uber]; todo = [(start, ())]; seen = set()
            while todo:
                pc, stack = todo.pop()
                while True:
                    if (pc, stack) in seen or pc not in self.idx: break
                    seen.add((pc, stack))
                    i = self.idx[pc]; x = us[i]; op = x[0]
                    stmt(self.uber, x)
                    nxt = us[i + 1].m if i + 1 < len(us) else None
                    if op == 0x06: pc = x[1]; continue
                    if op == 0x07: todo.append((x[1], stack)); pc = nxt; continue
                    if op == 0x4C: stack = (stack + (x[1],))[-16:]; pc = nxt; continue
                    if op == 0x4D:
                        if not stack: break
                        pc, stack = stack[-1], stack[:-1]; continue
                    if op == 0x4F:
                        if stack: todo.append((stack[-1], stack[:-1]))
                        pc = nxt; continue
                    if op in (0x04, 0x53, 0x4E): break
                    pc = nxt
        visit_func(event)
        return loads, seen_f

if __name__ == '__main__':
    b = BP(sys.argv[1])
    for ev in sys.argv[2:] or ['ReceiveTick']:
        loads, seen = b.reach(ev)
        print(ev, 'loads', len(loads), 'via', sorted(seen - {ev})[:40])
