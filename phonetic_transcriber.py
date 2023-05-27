#!/usr/bin/env python3

import os, json, re, sys, traceback
from collections import defaultdict

from phonetic_converter import PhoneticConverter, AlphabeticCharacterConverter


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


default_rules_path = os.path.join(basedir, 'rules.json')
default_exceptions_path = os.path.join(basedir, 'exceptions.json')


class PhoneticTranscriberData:

    def __init__(self, rules_filepath=default_rules_path, exceptions_filepath=default_exceptions_path):
        with open(exceptions_filepath, 'r') as f:
            self._exceptions = json.load(f)
        with open(rules_filepath, 'r') as f:
            data = json.load(f, object_hook=jsdict)
            self._metarules = data.metarules
            self._rules = data.rules

    @property
    def exceptions(self):
        return self._exceptions

    @property
    def metarules(self):
        return self._metarules

    @property
    def rules(self):
        return self._rules



class PhoneticTranscriber:

    def __init__(self, sep=' ', encoder=None, data=PhoneticTranscriberData()):
        self.sep = sep
        if encoder:
            self.converter = PhoneticConverter(AlphabeticCharacterConverter(), encoder)
        else:
            self.converter = None
        self.exceptions = data.exceptions
        self.metarules = data.metarules
        self.rules = defaultdict(list)
        for rule in data.rules:
            self.rules[rule.text[0]].append(rule)    # rules by first char

    def test_rule(self, rule, text, p):
        if p >= len(text) or p < 0:
            return False
        if not text[p:].startswith(rule.text):
            return False
        p2 = p
        p2 += len(rule.text)
        for subrule in rule.right:
            if subrule.tag == 'u':
                # unused text
                if not text[p2:].startswith(subrule.text):
                    return False
                p2 += len(subrule.text)
            elif subrule.tag == 'm':
                # metarule
                if subrule.text == '?':
                    # one char is allowed by metarule
                    if p2 >= len(text):
                        return False
                    p2 += 1
                elif subrule.text == '#':
                    # no chars can be left in source text
                    if p2 < len(text):
                        return False
                    break
                elif subrule.text == '^':
                    # there must be one or more chars to the right of the position:
                    if p2 >= len(text):
                        return False
                    break
                elif subrule.text == '*':
                    # there can be any amount of chars to the right, no more rules are processed
                    break
                else:
                    for t in self.metarules[subrule.text]:
                        if len(text) - p2 < len(t):
                            continue
                        if text[p2:].startswith(t):
                            p2 += len(t)
                            break
                    else:
                        return False
            else:
                return False

        p2 = p-1
        for subrule in rule.left:
            if subrule.tag == 'u':
                if p2 + 1 < len(subrule.text):
                    return False
                # unused text
                if not text[:p2+1].endswith(subrule.text):
                    return False
                p2 -= len(subrule.text)
            elif subrule.tag == 'm':
                # metarule
                if subrule.text == '?':
                    # one char is allowed by metarule
                    if p2 < 0:
                        return False
                    p2 -= 1
                elif subrule.text == '#':
                    # no chars can be left in source text
                    if p2 <= -1:
                        break
                    return False
                elif subrule.text == '^':
                    # there must be one or more chars to the left of the position:
                    if p2 >= 0:
                        break
                    else:
                        return False
                elif subrule.text == '*':
                    # there can be any amount of chars to the left, no more rules are processed
                    break
                else:
                    for t in self.metarules[subrule.text]:
                        if p2 + 1 < len(t):
                            continue
                        if text[:p2+1].endswith(t):
                            p2 -= len(t)
                            break
                    else:
                        return False
            else:
                return False
        return True

    def rules_transcribe(self, text):
        result = ''
        p = 0
        while p < len(text):
            rules = self.rules[text[p]]
            if not rules:
                return
            rule = None
            for r in rules:
                if self.test_rule(r, text, p):
                    rule = r
                    break
            if not rule:
                p += 1
                continue
            if not result or (rule.repl and rule.repl[0] == '#'):
                result += rule.repl
            else:
                result += '_' + rule.repl
            p += len(rule.text)
        return result

    def transcribe(self, word):
        # word = word.lower()
        result = self.exceptions.get(word)
        if not result:
            result = self.rules_transcribe(word)
        tokens = result.split("_")
        if self.converter:
            tokens = self.converter.convertTokens(tokens)
        if not tokens:
            return
        result = self.sep.join(tokens)
        return result

    def transcribePhrase(self, phrase):
        if not re.match(r'^[a-zēūīāšģķļžčņ\s]*$', phrase):
            raise Exception('Unrecognized symbols in string!')
        words = re.sub(r'\s+', ' ', phrase).strip().split(' ')
        transcribed = [self.transcribe(word) for word in words]
        return ' . '.join(transcribed)


def clean_text(text):
    text = text.lower()
    text = text.replace("w", "v");
    text = text.replace("q", "ku");
    text = text.replace("x", "ks");
    text = text.replace("y", "j");
    return text


def test_eq(expected, check):
    print('% 4s   expected: % 40s  got: % 40s' % ('OK' if expected == check else 'FAIL', expected, check))


def test(data=None):

    if not data:
        data = PhoneticTranscriberData()

    from phonetic_converter import AlphaNumericSimplifiedCharacterConverter, AlphaNumericCharacterConverter, IPACharacterConverter

    for testcase in [
                jsdict(input="apli", expected="a_p_l_ix", sep="_", encoder=None),
                jsdict(input="apģērbti", expected="a_p_G_EE_r_p_t_ix", sep="_", encoder=None),
                jsdict(input="ēķī", expected="ee_K_ii", sep="_", encoder=None),
                jsdict(input="sairt", expected="s a i r t", sep=" ", encoder=None),
                jsdict(input="saime", expected="s ai m e", sep=" ", encoder=None),
                jsdict(input="uzspiestu", expected="x", sep=" ", encoder=AlphaNumericCharacterConverter()),
                jsdict(input="ē", expected="EE", sep="_", encoder=None),
                jsdict(input="puškins", expected="p_u_S_k_i_n_s", sep="_", encoder=None),
                jsdict(input="nospiedošs", expected="n u035Co s p i035Ce d 0254 0283", sep=" ", encoder=AlphaNumericCharacterConverter()),
                jsdict(input="ma-tra-cis", expected="m a - t r a - ts ix s", sep=" ", encoder=AlphabeticCharacterConverter()),
                jsdict(input=("ō" or "\u014d"), expected="oo", sep=" ", encoder=AlphabeticCharacterConverter()),
                jsdict(input="atel'jē", expected="a t e l ' j ee", sep=" ", encoder=AlphabeticCharacterConverter()),
            ]:
        transcriber = PhoneticTranscriber(sep=testcase.sep, encoder=testcase.encoder, data=data)
        result = transcriber.transcribe(testcase.input)
        test_eq(testcase.expected, result)


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--rules', '-r', metavar='FILE', type=str, help='input rules.json')
    parser.add_argument('--exceptdb', '-e', metavar='FILE', type=str, help='input exceptions.json')
    parser.add_argument('--test', '-t', action='store_true', help='run test')
    parser.add_argument('--phrase', '-p', action='append', help='input phrase to transcribe')
    parser.add_argument('--json', '-j', metavar='FILE', type=str, help='output to json file, - to stdout')
    parser.add_argument('--tsv', metavar='FILE', type=str, help='output to Tab Separated Value file, - to stdout')
    parser.add_argument('--server', '-s', metavar='HOST:PORT', help='run server listening on [HOST]:PORT')
    parser.add_argument('word', nargs='*', type=str, help='input word to transcribe')

    args = parser.parse_args()

    data = PhoneticTranscriberData(rules_filepath=args.rules or default_rules_path, exceptions_filepath=args.exceptdb or default_exceptions_path)

    if args.test:
        print('testing')
        test(data)

    from phonetic_converter import IPACharacterConverter

    transcriber = PhoneticTranscriber(sep=' ', encoder=IPACharacterConverter(), data=data)

    if args.phrase or args.word:
        if args.json or args.tsv:
            result = []
            if args.phrase:
                for phrase in args.phrase:
                    r = jsdict(phrase=phrase)
                    try:
                        r.result = transcriber.transcribePhrase(clean_text(phrase))
                    except Exception as e:
                        print(traceback.format_exc(), file=sys.stderr)
                        r.error = str(e)
                    result.append(r)
            for word in args.word:
                r = jsdict(word=word)
                try:
                    r.result = transcriber.transcribe(clean_text(word))
                except Exception as e:
                    print(traceback.format_exc(), file=sys.stderr)
                    r.error = True
                result.append(r)

            if args.json:
                if args.json != '-':
                    print(f'writing to {args.json}', file=sys.stderr)
                with (sys.stdout if args.json == '-' else open(args.json, 'w')) as  f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                    print(file=f)

            if args.tsv:
                if args.tsv != '-':
                    print(f'writing to {args.tsv}', file=sys.stderr)
                with (sys.stdout if args.tsv == '-' else open(args.tsv, 'w')) as  f:
                    for r in result:
                        print(f'{r.word or r.phrase}\t{r.result or ""}\t{r.error or ""}', file=f)

        else:

            if args.phrase:
                for phrase in args.phrase:
                    print(f'transcribing phrase: {phrase}')
                    print(f'             result:', transcriber.transcribePhrase(clean_text(phrase)))

            for word in args.word:
                print(f'transcribing input: {word}', end=' ' * max(1, 20 - len(word)), flush=True)
                print('result:', transcriber.transcribe(clean_text(word)))

    if args.server:
        from server import run_server
        run_server(args.server, transcriber, debug=False)
