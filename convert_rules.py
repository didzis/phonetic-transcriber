#!/usr/bin/env python3

import re, json
# from collections import defaultdict


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


def load_exceptions_db(filename):
    result = {}
    ws_re = re.compile(r'\s+')
    with open(filename) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            key, value = ws_re.split(line)
            result[key] = value
    return result


def print_element(el, depth=0):
    if type(el.content) is str:
        print(f'{" " * depth}<{el.tag}>{el.content}</{el.tag}>')
    else:
        print(f'{" " * depth}<{el.tag}>')
        for childel in el.content:
            print_element(childel, depth + 1)
        print(f'{" " * depth}</{el.tag}>')


def load_rule_file(filename, debug=False):
    result = {}
    opentag_re = re.compile(r'^<(\w+)>$')
    closetag_re = re.compile(r'^</(\w+)>$')
    element_re = re.compile(r'^<(\w+)>([^<>]*)</(\w+)>$')
    with open(filename) as f:
        root = jsdict(tag='root', content=[], parent=None)
        current = root
        for line in f:
            line = line.strip()
            if not line:
                continue
            if debug:
                print('line:', line)
            opentag, closetag, element = (m.groups() if m else None for m in (r.match(line) for r in [opentag_re, closetag_re, element_re]))
            if opentag:
                if debug:
                    print('open: <%s>' % opentag[0])
                element = jsdict(tag=opentag[0], content=[], parent=current)
                current.content.append(element)
                current = element
            elif closetag:
                if debug:
                    print('close: </%s>' % closetag[0], 'current: <%s>' % current.tag)
                assert closetag[0] == current.tag
                assert current.parent is not None
                current = current.parent
            elif element:
                if debug:
                    print('element: <%s>%s</%s>' % element)
                assert element[0] == element[2]
                content = element[1]
                current.content.append(jsdict(tag=element[0], content=content, parent=current))

        return root


def convert_metarules(filename):
    metarules = {}
    for mr in load_rule_file(filename).content:
        assert mr.tag == 'm'
        d = None
        ts = []
        for mr in mr.content:
            if mr.tag == 'd':
                d = mr.content
            elif mr.tag == 't':
                ts.append(mr.content)
        metarules[d] = ts
    return metarules


def convert_rules(filename):
    rules = []
    # rulesByChar = defaultdict(list)
    for ruledef in load_rule_file("./jar/rules.xml").content:
        assert ruledef.tag == 'r'
        p = None
        t = None
        left = []
        right = []
        for child in ruledef.content:
            if child.tag == 'p':
                assert type(child.content) is str
                p = child.content
            elif child.tag == 'd':
                assert type(child.content) is list
                for child in child.content:
                    if child.tag == 't':
                        assert type(child.content) is str
                        t = child.content
                    elif child.tag == 'u' or child.tag == 'm':
                        assert type(child.content) is str
                        if t:
                            right.append(jsdict(tag=child.tag, text=child.content))
                        else:
                            left.append(jsdict(tag=child.tag, text=child.content))
        rule = jsdict(text=t, repl=p, left=list(reversed(left)), right=right)
        rules.append(rule)
        # rulesByChar[rule.text[0]].append(rule)    # rules by first char
    return rules


def convert_rules_and_metarules(metarules_filename='metas.xml', rules_filename='rules.xml', output_filename='rules.json', ensure_ascii=False, indent=2):
    print(f'loading {metarules_filename}')
    metarules = convert_metarules(metarules_filename)
    print(f'loading {rules_filename}')
    rules = convert_rules(rules_filename)
    print(f'writing {output_filename}')
    with open(output_filename, 'w') as f:
        json.dump(dict(metarules=metarules, rules=rules), f, indent=indent, ensure_ascii=ensure_ascii, sort_keys=True)


def convert_exceptions(filename, output_filename='exceptions.json', ensure_ascii=False, indent=2):
    print(f'loading {filename}')
    exceptions = load_exceptions_db(filename)
    print(f'writing {output_filename}')
    with open(output_filename, 'w') as f:
        json.dump(exceptions, f, indent=indent, ensure_ascii=ensure_ascii, sort_keys=True)



if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--meta', '-m', help='input metas.xml')
    parser.add_argument('--rules', '-r', help='input rules.xml')
    parser.add_argument('--exceptdb', '-e', help='input exceptionTranscriptions.db')
    parser.add_argument('--out', '-o', default='rules.json', help='output json for combined rules and materules')
    parser.add_argument('--except-out', '--eo', default='exceptions.json', help='output json for exception db')
    parser.add_argument('--ensure-ascii', action='store_true', default=False, help='output ascii json')

    args = parser.parse_args()

    if args.meta and args.rules and args.out:
        convert_rules_and_metarules(args.meta, args.rules, args.out, ensure_ascii=args.ensure_ascii)

    if args.exceptdb and args.except_out:
        convert_exceptions(args.exceptdb, args.except_out, ensure_ascii=args.ensure_ascii)
