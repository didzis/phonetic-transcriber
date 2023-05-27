#!/usr/bin/env python3

import os, json


class jsdict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def __getattr__(self, name):
        return self.get(name)
    def __setattr__(self, name, value):
        self[name] = value
    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            pass

basedir = os.path.dirname(__file__)

# To convert dataset json from ascii to unicode json:
# $ python3 -m json.tool --indent 2 --no-ensure-ascii --sort-keys phonetic_converter_dataset_ascii.json phonetic_converter_dataset_unicode.json

dataset = None

def load_dataset(filepath=os.path.join(basedir, 'phonetic_converter_dataset.json')):
    global dataset
    with open(filepath, 'r') as f:
        dataset = json.load(f, object_hook=jsdict)


class AlphaNumericSimplifiedCharacterConverter:

    def __init__(self):
        if not dataset:
            load_dataset()
        data = dataset.AlphaNumericSimplifiedCharacterConverter
        self.fromIPAafter = data.fromIPAafter
        self.fromIPAbefore = data.fromIPAbefore
        self.fromIPAresult = data.fromIPAresult

    def toIPAchar(self, char):
        return

    def fromIPAchar(self, char):
        if len(char) > 1:
            after = self.fromIPAafter.get(char[len(char)-1])
            before = self.fromIPAbefore.get(char[0])
            if after:
                char = char[0:len(char)-1]
            if before:
                char = char[1:]
        result = self.fromIPAresult.get(char)
        return result

    def tokenize(self, word):
        return


class AlphaNumericCharacterConverter:

    def __init__(self):
        if not dataset:
            load_dataset()
        data = dataset.AlphaNumericCharacterConverter
        self.toIPAafter = data.toIPAafter
        self.toIPAbefore = data.toIPAbefore
        self.toIPAresult = data.toIPAresult
        self.fromIPAafter = data.fromIPAafter
        self.fromIPAbefore = data.fromIPAbefore
        self.fromIPAresult = data.fromIPAresult

    def toIPAchar(self, char):
        after = None
        before = None
        if len(char) > 4:
            after = self.toIPAafter.get(char[len(char)-4:])
            before = self.toIPAbefore.get(char[0:4])
            if after:
                char = char[0:len(char)-4]
            if before:
                char = char[4:]

        result = self.toIPAresult.get(char)

        if not result:
            return
        if before:
            result = before + result
        if after:
            result += after

        return result

    def fromIPAchar(self, char):
        after = None
        before = None

        if len(char) > 1:
            after = self.fromIPAafter.get(char[len(char)-1])
            before = self.fromIPAbefore.get(char[0])
            if after:
                char = char[0:len(char)-1]
            if before:
                char = char[1:]

        result = self.fromIPAresult.get(char)

        if not result:
            return
        if before:
            result = before + result
        if after:
            result += after

        return result


class AlphabeticCharacterConverter:

    def __init__(self):
        if not dataset:
            load_dataset()
        data = dataset.AlphabeticCharacterConverter
        self.toIPAafter = data.toIPAafter
        self.toIPAbefore = data.toIPAbefore
        self.toIPAresult = data.toIPAresult
        self.fromIPAafter = data.fromIPAafter
        self.fromIPAbefore = data.fromIPAbefore
        self.fromIPAresult = data.fromIPAresult

    def toIPAchar(self, char):
        after = None
        before = None
        if len(char) >= 1:
            after = self.toIPAafter.get(char[len(char)-1])
            before = self.toIPAbefore.get(char[0])
            if after:
                char = char[0:len(char)-1]
            if before:
                char = char[1:]

        result = self.toIPAresult.get(char)

        if not result:
            result = ""
            # return
        if before:
            result = before + result
        if after:
            result += after

        return result

    def fromIPAchar(self, char):
        after = None
        before = None
        if len(char) > 0:
            after = self.fromIPAafter.get(char[len(char)-1])
            before = self.fromIPAbefore.get(char[0])
            if len(char) > 2 and char[len(char)-1] == '\u02d0':
                after = "="
            if after:
                char = char[0:len(char)-1]
            if before:
                char = char[1:]

        result = self.fromIPAresult.get(char)

        if not result:
            result = ""
            # return
        if before:
            result = before + result
        if after:
            result += after

        return result

    def tokenize(self, word):
        return


class IPASimplifiedCharacterConverter:

    def __init__(self):
        if not dataset:
            load_dataset()
        data = dataset.IPASimplifiedCharacterConverter
        self.fromIPAafter = data.fromIPAafter
        self.fromIPAbefore = data.fromIPAbefore
        self.fromIPAresult = data.fromIPAresult
        self.charsets = data.charsets

    def toIPAchar(self, char):
        return char

    def fromIPAchar(self, char):
        if len(char) > 1:
            after = self.fromIPAafter.get(char[len(char)-1])
            before = self.fromIPAbefore.get(char[0])
            if len(char) > 2 and char[len(char)-1] == '\u02d0':
                after = "="
            if after:
                char = char[0:len(char)-1]
            if before:
                char = char[1:]

        return self.fromIPAresult.get(char)

    def tokenize(self, word):
        tokens = []
        state = 0
        token = ""
        for i, c in enumerate(word):
            if state == 0:
                if (c in self.charsets[0] or c in self.charsets[1]) and i > 0:
                    tokens.append(token);
                    token = "";
                if c in self.charsets[0] or c == self.charsets[2]:
                    state=1;
                token += c;
            elif state == 1:
                token += c;
                state = 0
        return tokens


class IPACharacterConverter:

    def __init__(self):
        if not dataset:
            load_dataset()
        self.charsets = dataset.IPACharacterConverter.charsets

    def toIPAchar(self, char):
        return char

    def fromIPAchar(self, char):
        return char

    def tokenize(self, word):
        tokens = []
        state = 0
        token = ""
        for i, c in enumerate(word):
            if state == 0:
                if (c in self.charsets[0] or c in self.charsets[1]) and i > 0:
                    tokens.append(token);
                    token = "";
                if c in self.charsets[0] or c == self.charsets[2]:
                    state=1;
                token += c;
            elif state == 1:
                token += c;
                state = 0
        return tokens


class PhoneticConverter:

    def __init__(self, decoder=None, encoder=None):
        self.decoder = decoder
        self.encoder = encoder

    def convertChar(self, char):
        token = self.decoder.toIPAchar(character)
        token = self.encoder.fromIPAchar(token)
        return token

    def convertTokens(self, tokens):
        return [self.encoder.fromIPAchar(self.decoder.toIPAchar(token)) for token in tokens]

    def convert(self, word, separator = ''):
        tokens = self.decoder.tokenize(word);
        if not tokens:
            return
        tokens = self.convertTokens(tokens)
        return separator.join(tokens)


def test():

    def test_eq(a, b):
        print('% 4s   expected: % 8s    got: % 8s' % ('OK' if a == b else 'FAIL', a, b))

    converter = AlphabeticCharacterConverter()

    test_eq("%", converter.fromIPAchar("\u02cc"))
    test_eq("\u02cc", converter.toIPAchar("%"))
    test_eq("\"", converter.fromIPAchar("\u02c8"))
    test_eq("\u02c8", converter.toIPAchar("\""))
    test_eq("aq", converter.fromIPAchar("\u0251\u02c0"))
    test_eq("\u0251\u02c0", converter.toIPAchar("aq"))
    test_eq("aa=", converter.fromIPAchar("\u0251\u02d0\u02d0"))
    test_eq("\u0251\u02d0\u02d0", converter.toIPAchar("aa="))
    test_eq("aa=", converter.fromIPAchar(converter.toIPAchar("aa=")))

if __name__ == '__main__':

    load_dataset()

    test()
