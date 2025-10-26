from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional, Set, Dict, Any


# ---------------- Lexer ----------------

class Token:
    def __init__(self, typ: str, val: Optional[str] = None):
        self.typ = typ
        self.val = val

    def __repr__(self):
        return f"Token({self.typ},{self.val})"


def tokenize(s: str) -> List[Token]:
    import re
    i = 0
    toks: List[Token] = []
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1;
            continue
        if s.startswith('->', i) or s.startswith('→', i):
            toks.append(Token('IMPLIES', '->'));
            i += 2 if s.startswith('->', i) else 1;
            continue
        if c in '()':
            toks.append(Token(c, c));
            i += 1;
            continue
        if c in '!¬':
            toks.append(Token('NOT', c));
            i += 1;
            continue
        if c in '&∧':
            toks.append(Token('AND', c));
            i += 1;
            continue
        if c in '|∨':
            toks.append(Token('OR', c));
            i += 1;
            continue
        if c == 'G':
            toks.append(Token('G', 'G'));
            i += 1;
            continue
        if c == 'F':
            toks.append(Token('F', 'F'));
            i += 1;
            continue
        if c == 'X':
            # maybe X^n
            j = i + 1
            if j < len(s) and s[j] == '^':
                k = j + 1
                num = ''
                while k < len(s) and s[k].isdigit():
                    num += s[k];
                    k += 1
                if not num:
                    raise ValueError('После X^ ожидается число')
                toks.append(Token('XPOW', num))
                i = k
            else:
                toks.append(Token('X', 'X'));
                i += 1
            continue
        if s.startswith('U', i):
            toks.append(Token('U', 'U'));
            i += 1;
            continue

        m = re.match(r'[A-Za-zА-Яа-яЁё_][A-Za-z0-9А-Яа-яЁё_]*', s[i:])
        if m:
            ident = m.group(0)
            toks.append(Token('ID', ident))
            i += len(ident);
            continue

        raise ValueError(f'Неожиданный символ в формуле: {c!r} at {i}')
    return toks


# ---------------- AST ----------------

@dataclass
class Node: ...


@dataclass
class Pred(Node):
    name: str


@dataclass
class Not(Node):
    child: Node


@dataclass
class And(Node):
    left: Node;
    right: Node


@dataclass
class Or(Node):
    left: Node;
    right: Node


@dataclass
class Implies(Node):
    left: Node;
    right: Node


@dataclass
class Next(Node):
    child: Node;
    k: int = 1


@dataclass
class Until(Node):
    left: Node;
    right: Node


@dataclass
class Globally(Node):
    child: Node


@dataclass
class Finally(Node):
    child: Node


@dataclass
class Bool(Node):
    val: bool


# ---------------- Parser (precedence) ----------------

class Parser:
    def __init__(self, tokens: List[Token]):
        self.toks = tokens;
        self.pos = 0

    def peek(self) -> Optional[Token]:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def eat(self, typ: Optional[str] = None) -> Token:
        t = self.peek()
        if t is None:
            raise ValueError('Неожиданный конец формулы')
        if typ and t.typ != typ:
            raise ValueError(f'Ожидался {typ}, но {t.typ}')
        self.pos += 1;
        return t

    def parse(self) -> Node:
        node = self.parse_implication()
        if self.peek() is not None:
            raise ValueError('Лишний хвост в формуле')
        return node

    def parse_implication(self) -> Node:
        left = self.parse_or()
        t = self.peek()
        if t and t.typ == 'IMPLIES':
            self.eat('IMPLIES')
            right = self.parse_implication()
            return Implies(left, right)
        return left

    def parse_or(self) -> Node:
        node = self.parse_and()
        while True:
            t = self.peek()
            if t and t.typ == 'OR':
                self.eat('OR')
                node = Or(node, self.parse_and())
            else:
                break
        return node

    def parse_and(self) -> Node:
        node = self.parse_until()
        while True:
            t = self.peek()
            if t and t.typ == 'AND':
                self.eat('AND')
                node = And(node, self.parse_until())
            else:
                break
        return node

    def parse_until(self) -> Node:
        node = self.parse_unary()
        t = self.peek()
        if t and t.typ == 'U':
            self.eat('U')
            right = self.parse_unary()
            return Until(node, right)
        return node

    def parse_unary(self) -> Node:
        t = self.peek()
        if t is None:
            raise ValueError('Ожидался унарный оператор/скобка/идентификатор')
        if t.typ == 'NOT':
            self.eat('NOT')
            return Not(self.parse_unary())
        if t.typ == 'G':
            self.eat('G')
            return Globally(self.parse_unary())
        if t.typ == 'F':
            self.eat('F')
            return Finally(self.parse_unary())
        if t.typ == 'X':
            self.eat('X')
            return Next(self.parse_unary(), k=1)
        if t.typ == 'XPOW':
            k = int(self.eat('XPOW').val or '1')
            return Next(self.parse_unary(), k=k)
        if t.typ == '(':
            self.eat('(')
            node = self.parse_implication()
            self.eat(')')
            return node
        if t.typ == 'ID':
            name = self.eat('ID').val
            if name.upper() == 'TRUE': return Bool(True)
            if name.upper() == 'FALSE': return Bool(False)
            return Pred(name)
        raise ValueError(f'Неожиданный токен: {t}')


# ---------------- Macro expansion helpers ----------------

def expand_macros(formula: str) -> str:
    import re

    def repl_within(match: re.Match) -> str:
        inner = match.group('phi').strip()
        k = int(match.group('k'))
        parts = []
        for i in range(1, k + 1):
            if i == 1:
                parts.append(f"X ({inner})")
            else:
                parts.append(f"X^{i} ({inner})")
        return ' ∨ '.join(parts)

    pattern = re.compile(r"Within_k\( (?P<phi>.+?) , \s*(?P<k>\d+) \)", re.X)

    prev = None
    while prev != formula:
        prev = formula
        formula = re.sub(pattern, repl_within, formula)

    pattern2 = re.compile(r"NoNext\( (?P<phi>.+?) \)", re.X)
    while True:
        newf = re.sub(pattern2, lambda m: f"¬X ({m.group('phi')})", formula)
        if newf == formula: break
        formula = newf
    return formula


# ---------------- Evaluation ----------------

def eval_formula(node: Node, trace: List[Dict[str, bool]], i: int = 0) -> bool:
    n = len(trace)

    def ev(nod: Node, pos: int) -> bool:
        if isinstance(nod, Bool): return nod.val
        if isinstance(nod, Pred):
            return bool(trace[pos].get(nod.name, False)) if 0 <= pos < n else False
        if isinstance(nod, Not):
            return not ev(nod.child, pos)
        if isinstance(nod, And):
            return ev(nod.left, pos) and ev(nod.right, pos)
        if isinstance(nod, Or):
            return ev(nod.left, pos) or ev(nod.right, pos)
        if isinstance(nod, Implies):
            return (not ev(nod.left, pos)) or ev(nod.right, pos)
        if isinstance(nod, Next):
            nxt = pos + nod.k
            if nxt >= n: return False
            return ev(nod.child, nxt)
        if isinstance(nod, Finally):
            for j in range(pos, n):
                if ev(nod.child, j): return True
            return False
        if isinstance(nod, Globally):
            for j in range(pos, n):
                if not ev(nod.child, j): return False
            return True
        if isinstance(nod, Until):
            for j in range(pos, n):
                if ev(nod.right, j):
                    for k in range(pos, j):
                        if not ev(nod.left, k): return False
                    return True
            return False
        raise TypeError('Неизвестный узел')

    return ev(node, i)


def parse_formula(s: str) -> Node:
    s = expand_macros(s)
    tokens = tokenize(s)
    return Parser(tokens).parse()


def build_trace_from_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, bool]]:
    res = []
    for st in steps:
        d: Dict[str, bool] = {}
        for e in st.get('events', []):
            d[e] = True

        state = st.get('state')
        if state:
            d[f'S_{state}'] = True

        res.append(d)
    return res
