"""Phase 3 / Component E: minimal strict JSON object codec.

Mojo 1.2.0 has no ``json`` module (verified by compile probes). Rather than a
fragile general-purpose parser, this module implements a deliberately narrow,
strict reader/writer for a FLAT JSON object whose values are only strings,
numbers, booleans or ``null``. That is exactly what the golden-vector schema
and the coefficient-resource metadata need.

Strictness rules (all violations are actionable errors, never silent):
- exactly one top-level object; nested objects and arrays are rejected;
- keys must be double-quoted strings; duplicate/unknown keys are handled by
  the caller via ``keys()``/``has()``;
- values: quoted string, integer, decimal/exponent number, true/false/null;
- no trailing content, no comments, no single quotes, no bare identifiers;
- string escapes supported: quote, backslash, slash, b, f, n, r, t and
  the BMP Unicode escape (4 hex digits).
- every parsed number must be FINITE: overflow to infinity and NaN are rejected;
- serialization never emits bare ``inf``/``nan`` (invalid JSON) — non-finite
  inputs are rejected with an actionable error.

This is a deliberately narrow JSON subset, not a full RFC 8259 implementation.
Serialization emits a deterministic, canonical flat object (fixed key order
supplied by the caller), so byte-for-byte reproducible metadata is possible.
"""

from std.collections import Dict, List
from std.math import isnan, isinf


comptime JSON_NULL: UInt8 = 0
comptime JSON_BOOL: UInt8 = 1
comptime JSON_INT: UInt8 = 2
comptime JSON_FLOAT: UInt8 = 3
comptime JSON_STRING: UInt8 = 4


struct JsonValue(Copyable, Movable, ImplicitlyCopyable):
    """A tagged scalar JSON value. ``text`` holds the decoded string or raw number."""

    var kind: UInt8
    var text: String

    def __init__(out self, kind: UInt8, text: String):
        self.kind = kind
        self.text = text


struct JsonObject(Copyable, Movable):
    """An ordered flat JSON object (insertion order preserved for serialization)."""

    var _values: Dict[String, JsonValue]
    var _order: List[String]

    def __init__(out self):
        self._values = Dict[String, JsonValue]()
        self._order = List[String]()

    def set(mut self, key: String, value: JsonValue) raises:
        if key in self._values:
            raise Error("duplicate JSON key '" + key + "'")
        self._values[key] = value
        self._order.append(key)

    def set_string(mut self, key: String, value: String) raises:
        self.set(key, JsonValue(JSON_STRING, value))

    def set_int(mut self, key: String, value: Int) raises:
        self.set(key, JsonValue(JSON_INT, String(value)))

    def set_float(mut self, key: String, value: Float64) raises:
        if isnan(value) or isinf(value):
            raise Error("cannot serialize non-finite Float64 as JSON number for key '" + key + "'")
        self.set(key, JsonValue(JSON_FLOAT, String(value)))

    def set_bool(mut self, key: String, value: Bool) raises:
        self.set(key, JsonValue(JSON_BOOL, "true" if value else "false"))

    def set_null(mut self, key: String) raises:
        self.set(key, JsonValue(JSON_NULL, "null"))

    def has(self, key: String) -> Bool:
        return key in self._values

    def keys(self) -> List[String]:
        var out = List[String]()
        for key in self._order:
            out.append(key)
        return out^

    def get(self, key: String) raises -> JsonValue:
        if key not in self._values:
            raise Error("missing JSON key '" + key + "'")
        return self._values[key]

    def get_string(self, key: String) raises -> String:
        var value = self.get(key)
        if value.kind != JSON_STRING:
            raise Error("JSON key '" + key + "' must be a string")
        return value.text

    def get_int(self, key: String) raises -> Int:
        var value = self.get(key)
        if value.kind != JSON_INT:
            raise Error("JSON key '" + key + "' must be an integer")
        return Int(value.text)

    def get_float(self, key: String) raises -> Float64:
        var value = self.get(key)
        if value.kind not in (JSON_INT, JSON_FLOAT):
            raise Error("JSON key '" + key + "' must be a number")
        var parsed = Float64(value.text)
        if isnan(parsed) or isinf(parsed):
            raise Error(
                "JSON key '" + key + "' has non-finite numeric value '" + value.text + "'"
            )
        return parsed

    def get_bool(self, key: String) raises -> Bool:
        var value = self.get(key)
        if value.kind != JSON_BOOL:
            raise Error("JSON key '" + key + "' must be a boolean")
        return value.text == "true"

    def is_null(self, key: String) raises -> Bool:
        return self.get(key).kind == JSON_NULL

    def serialize(self) raises -> String:
        """Emit a canonical flat JSON object in the recorded key order."""
        var out = String("{")
        for i in range(len(self._order)):
            if i > 0:
                out += ", "
            var key = self._order[i]
            var value = self._values[key]
            out += _quote(key) + ": "
            if value.kind == JSON_STRING:
                out += _quote(value.text)
            else:
                out += value.text
        out += "}"
        return out


def _quote(text: String) raises -> String:
    """JSON-escape a string (control characters, quote, backslash)."""
    var out = String("\"")
    for byte in text.as_bytes():
        if byte == 34:
            out += "\\\""
        elif byte == 92:
            out += "\\\\"
        elif byte == 8:
            out += "\\b"
        elif byte == 9:
            out += "\\t"
        elif byte == 10:
            out += "\\n"
        elif byte == 12:
            out += "\\f"
        elif byte == 13:
            out += "\\r"
        elif byte < 32:
            out += "\\u00" + _hex2(byte)
        else:
            var one = List[UInt8](capacity=1)
            one.append(byte)
            out += String(from_utf8=Span(one))
    out += "\""
    return out


def _hex2(byte: UInt8) raises -> String:
    comptime DIGITS: String = "0123456789abcdef"
    var two = List[UInt8](capacity=2)
    two.append(DIGITS.as_bytes()[Int(byte >> 4)])
    two.append(DIGITS.as_bytes()[Int(byte & 0x0F)])
    return String(from_utf8=Span(two))


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_json_object(text: String) raises -> JsonObject:
    """Parse one flat JSON object. Reject anything outside the narrow grammar."""
    var p = _Parser(text)
    p.skip_ws()
    p.expect("{")
    var obj = JsonObject()
    p.skip_ws()
    if p.peek() == 125:  # '}'
        p.advance()
        p.skip_ws()
        p.require_end()
        return obj^
    while True:
        p.skip_ws()
        if p.peek() != 34:
            p.fail("expected a double-quoted key")
        var key = p.parse_string()
        p.skip_ws()
        p.expect(":")
        p.skip_ws()
        var value = p.parse_value()
        obj.set(key, value)
        p.skip_ws()
        var c = p.peek()
        if c == 44:  # ','
            p.advance()
            continue
        elif c == 125:  # '}'
            p.advance()
            break
        else:
            p.fail("expected ',' or '}'")
    p.skip_ws()
    p.require_end()
    return obj^


struct _Parser(Copyable, Movable):
    var _bytes: List[UInt8]
    var _pos: Int

    def __init__(out self, text: String):
        self._bytes = List[UInt8](capacity=text.byte_length())
        for byte in text.as_bytes():
            self._bytes.append(byte)
        self._pos = 0

    def peek(self) raises -> UInt8:
        if self._pos >= len(self._bytes):
            self.fail("unexpected end of JSON input")
        return self._bytes[self._pos]

    def advance(mut self) raises:
        if self._pos >= len(self._bytes):
            self.fail("unexpected end of JSON input")
        self._pos += 1

    def fail(self, message: String) raises:
        raise Error("JSON parse error at byte " + String(self._pos) + ": " + message)

    def skip_ws(mut self):
        while self._pos < len(self._bytes):
            var c = self._bytes[self._pos]
            if c == 32 or c == 9 or c == 10 or c == 13:
                self._pos += 1
            else:
                break

    def expect(mut self, token: String) raises:
        for byte in token.as_bytes():
            if self.peek() != byte:
                self.fail("expected '" + token + "'")
            self.advance()

    def require_end(self) raises:
        if self._pos != len(self._bytes):
            self.fail("trailing content after top-level object")

    def parse_string(mut self) raises -> String:
        self.expect("\"")
        var out = List[UInt8]()
        while True:
            var c = self.peek()
            if c == 34:  # closing quote
                self.advance()
                break
            elif c == 92:  # backslash escape
                self.advance()
                var esc = self.peek()
                self.advance()
                if esc == 34:
                    out.append(34)
                elif esc == 92:
                    out.append(92)
                elif esc == 47:
                    out.append(47)
                elif esc == 98:
                    out.append(8)
                elif esc == 102:
                    out.append(12)
                elif esc == 110:
                    out.append(10)
                elif esc == 114:
                    out.append(13)
                elif esc == 116:
                    out.append(9)
                elif esc == 117:  # \uXXXX (BMP, encoded as UTF-8)
                    var code: UInt32 = 0
                    for _ in range(4):
                        var h = self.peek()
                        self.advance()
                        var nib: UInt32 = 0
                        if h >= 48 and h <= 57:
                            nib = UInt32(h - 48)
                        elif h >= 97 and h <= 102:
                            nib = UInt32(h - 87)
                        elif h >= 65 and h <= 70:
                            nib = UInt32(h - 55)
                        else:
                            self.fail("invalid \\u hex digit")
                        code = (code << 4) | nib
                    if code < 0x80:
                        out.append(UInt8(code))
                    elif code < 0x800:
                        out.append(UInt8(0xC0 | (code >> 6)))
                        out.append(UInt8(0x80 | (code & 0x3F)))
                    else:
                        out.append(UInt8(0xE0 | (code >> 12)))
                        out.append(UInt8(0x80 | ((code >> 6) & 0x3F)))
                        out.append(UInt8(0x80 | (code & 0x3F)))
                else:
                    self.fail("unsupported string escape")
            elif c < 32:
                self.fail("raw control character in JSON string")
            else:
                out.append(c)
                self.advance()
        return String(from_utf8=Span(out))

    def parse_value(mut self) raises -> JsonValue:
        var c = self.peek()
        if c == 34:
            return JsonValue(JSON_STRING, self.parse_string())
        if c == 123 or c == 91:
            self.fail("nested objects and arrays are not supported")
        if c == 116:
            self.expect("true")
            return JsonValue(JSON_BOOL, "true")
        if c == 102:
            self.expect("false")
            return JsonValue(JSON_BOOL, "false")
        if c == 110:
            self.expect("null")
            return JsonValue(JSON_NULL, "null")
        if c == 45 or (c >= 48 and c <= 57):
            return self.parse_number()
        raise Error("JSON parse error at byte " + String(self._pos) + ": unexpected value token")

    def parse_number(mut self) raises -> JsonValue:
        var start = self._pos
        var is_float = False
        if self._pos < len(self._bytes) and self._bytes[self._pos] == 45:
            self._pos += 1
        if self.peek() == 48:
            self.advance()
            if self._pos < len(self._bytes) and self._bytes[self._pos] >= 48 and self._bytes[self._pos] <= 57:
                self.fail("leading zero in JSON number")
        else:
            var digits = 0
            while self._pos < len(self._bytes) and self._bytes[self._pos] >= 48 and self._bytes[self._pos] <= 57:
                self._pos += 1
                digits += 1
            if digits == 0:
                self.fail("expected digits in JSON number")
        if self._pos < len(self._bytes) and self._bytes[self._pos] == 46:
            is_float = True
            self._pos += 1
            var frac = 0
            while self._pos < len(self._bytes) and self._bytes[self._pos] >= 48 and self._bytes[self._pos] <= 57:
                self._pos += 1
                frac += 1
            if frac == 0:
                self.fail("expected digits after decimal point")
        if self._pos < len(self._bytes) and (self._bytes[self._pos] == 101 or self._bytes[self._pos] == 69):
            is_float = True
            self._pos += 1
            if self._pos < len(self._bytes) and (self._bytes[self._pos] == 43 or self._bytes[self._pos] == 45):
                self._pos += 1
            var exp = 0
            while self._pos < len(self._bytes) and self._bytes[self._pos] >= 48 and self._bytes[self._pos] <= 57:
                self._pos += 1
                exp += 1
            if exp == 0:
                self.fail("expected digits in exponent")
        var raw = String(from_utf8=Span(self._bytes[start : self._pos]))
        if is_float:
            # Detect conversion overflow/NaN at parse time so no field can
            # silently become infinity (e.g. 1e400 or -1e400).
            var parsed = Float64(raw)
            if isnan(parsed) or isinf(parsed):
                self.fail("numeric value '" + raw + "' is not finite")
        return JsonValue(JSON_FLOAT if is_float else JSON_INT, raw)
