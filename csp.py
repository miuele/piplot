from typing import NamedTuple

class Token(NamedTuple):
    ty: str
    value: str

class LineCursor:
    def __init__(self, src):
        self._src = src
        self._cursor = 0

    def _char_at(self, n):
        if n < len(self._src) and (c := self._src[n]) != '\n':
            return c
        return None

    def getchar(self):
        return self._char_at(self._cursor)

    def bump(self):
        if self._cursor < len(self._src):
            self._cursor += 1
        return self.getchar()

    def peekchar(self):
        return self._char_at(self._cursor + 1)

class ParseError(Exception):
    def __init__(self, msg):
        super().__init__(msg)

def csp_is_raw_term_char(c):
    return (c.isalpha() or c.isdigit() or
            c in '.+-_')

def csp_is_quoted_term_char(c):
    return c.is_printable() and c != '\n' and c != '"'

def csp_is_bracket_term_char(c):
    return csp_is_quoted_term_char() or c == '"'

def csp_lex_raw_term(cursor):
    term = cursor.getchar()
    cursor.bump()
    while True:
        c = cursor.getchar()
        if c and csp_is_raw_term_char(c):
            term += c
            cursor.bump()
        else:
            break
    return term

def csp_lex_quoted_term(cursor):
    cursor.bump() # skip '"'
    term = ''
    while True:
        c = cursor.getchar()
        if not c:
            raise ParseError("unterminated term")
        elif c == '"':
            cursor.bump()
            break

        term += c
        cursor.bump()

    return term

def csp_lex_bracket_term(cursor):
    term = cursor.getchar() # should be '{'
    cursor.bump()
    level = 1
    while level > 0:
        c = cursor.getchar()
        if not c:
            raise ParseError("unterminated bracket term")
        elif c == '"':
            term += c + csp_lex_quoted_term(cursor)
        elif c == '{':
            level += 1
        elif c == '}':
            level -= 1

        term += c
        cursor.bump()
    
    return term

def csp_lex_meta(cursor):
    cursor.bump() # skip '!'
    return bump_line(cursor)

def bump_line(cursor):
    s = ''
    while True:
        c = cursor.getchar()
        if not c:
            break
        s += c
        cursor.bump()
    return s

def csp_lex(s):
    cursor = LineCursor(s)
    meta = None

    while True:
        c = cursor.getchar()
        if not c:
            return meta
        elif c == ' ' or c == '\t':
            cursor.bump()
            continue
        elif c == '"':
            yield Token('term', csp_lex_quoted_term(cursor))
        elif c == '{':
            yield Token('term', csp_lex_bracket_term(cursor))
        elif c == ':':
            cursor.bump()
            yield Token(':', ':')
        elif c == ',':
            cursor.bump()
            yield Token(',', ',')
        elif c == '!':
            meta = csp_lex_meta(cursor)
        elif c == '#':
            bump_line(cursor)
        elif csp_is_raw_term_char(c):
            yield Token('term', csp_lex_raw_term(cursor))
        else:
            ParseError("invalid character: {}".format(c))

def csp_parse_pair(lexer):
    token = lexer.get() # type: term
    if lexer.peek1().ty == ':':
        lexer.bump()
        if lexer.bump().ty != 'term':
            raise ParseError('value term expected')
        tag = token
        value = lexer.get().value
        lexer.bump()
        return (token.value, value)
    else:
        lexer.bump()
        return (None, token.value)

def parse(s):
    class Lexer():
        def __init__(self, s):
            self._lexer = csp_lex(s)
            self._token = self._lexer_advance()
            self._ahead = self._lexer_advance()
            self._meta = None

        def _lexer_advance(self):
            if self._lexer:
                try:
                    return next(self._lexer)
                except StopIteration as e:
                    self._lexer = None
                    self._meta = e.value

            return Token('end', '\n')

        def peek1(self):
            return self._ahead
        
        def get(self):
            return self._token

        def bump(self):
            self._token = self._ahead
            self._ahead = self._lexer_advance()
            return self.get()

        @property
        def meta(self):
            return self._meta

    pairs = dict()
    anon_tag = 0

    lexer = Lexer(s)
    while True:
        token = lexer.get()
        if token.ty == 'end':
            break
        elif token.ty == 'term':
            tag, value = csp_parse_pair(lexer)
            if not tag:
                tag = anon_tag
                anon_tag += 1
            pairs[tag] = value

            sep = lexer.get().ty
            if sep == ',':
                lexer.bump()
            elif sep == 'end':
                pass
            else:
                raise ParseError('bad token after pair {}: {}'.format(token, sep))
        elif token.ty == ':':
            token = lexer.bump()
            if token.ty == 'term':
                value = token.value
                lexer.bump()
            elif token.ty == ',':
                value = ''
                lexer.bump()
            elif token.ty == 'end':
                value = ''
            else:
                raise ParseError('bad token {}'.format(token))

            pairs[''] = value

        elif token.ty == ',':
            pairs[anon_tag] = ''
            anon_tag += 1
            lexer.bump()
        else:
            raise ParseError("unexpected token {}".format(token))

    return pairs, lexer.meta

