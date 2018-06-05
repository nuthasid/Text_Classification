
def parse_topgun(f_path, b_path=None):

    import os
    import json
    from bs4 import BeautifulSoup as BS

    if not b_path:
        b_path = os.getcwd()

    f_path = os.path.join(b_path, f_path)

    with open(f_path, 'rt', encoding='utf-8') as page:
        page = BS(page.read(), "html5lib")

    header = page.find('script', attrs={'type': 'application/ld+json'}).get_text()

    title = json.load(header)

    print(title)


def find_next(text, sub, incr, pos=0):
    """Find the position within 'text' the string 'sub' that occur 'incr' times from the beginning position 'pos'
    """

    sub_pos = text.find(sub, pos)
    if sub_pos == -1:
        return None

    while incr > 0:
        sub_pos = text.find(sub, pos)
        pos = sub_pos + 1
        if sub_pos == -1:
            return None
        incr += -1

    return sub_pos


def find_left_occur(text, subs, pos=0):
    """"Return an element in 'sub' which occurs first in string 'text' beginning from position 'pos'."""
    ret_lst = [None, len(text)]

    for sub in subs:
        sub_pos = text.find(sub, pos)
        if sub_pos < ret_lst[1] and not sub_pos == -1:
            ret_lst = [sub, sub_pos]

    if ret_lst[0]:
        return ret_lst
    else:
        return [None, None]


def find_match_closure(text, m_open, m_close, begin=0, f_end=None):
    """Find the first sequence of string in 'text' which is enclosed in 'm_open' and 'm_close'.
    Beginning and ending parameters are optional.
    """

    if not f_end:
        f_end = len(text)
    f_start = text.find(m_open, begin)
    c_open = 0
    c_close = 0
    if f_start == -1:
        return None
    elif m_open == m_close:
        return text[text.find(m_open, begin):text.find(m_open, text.find(m_open, begin) + 1) + 1], \
                   text.find(m_open, text.find(m_open, begin) + 1) + 1
    else:
        c_open += 1
        f_start += 1
    while True:
        next_occur = find_left_occur(text[:f_end], [m_open, m_close], pos=f_start)
        if not next_occur[0]:
            return None
        elif next_occur[0] == m_open:
            c_open += 1
        else:
            c_close += 1
        f_start = next_occur[1] + 1
        if c_open == c_close:
            return text[text.find(m_open, begin):next_occur[1] + 1], next_occur[1] + 1


def parse_json(j_string):
    """Parse JSON formatted text into python dictionary"""

    j_string = j_string[j_string.find('{') + 1: j_string.rfind('}')].strip()
    json_dict = {}
    start = 0
    sep = j_string.find(':')

    while not sep == -1:
        j_string = j_string[j_string.find('"', start):]
        sep = j_string.find(':')
        if find_left_occur(j_string, ['"', '{'], pos=sep)[0] == '"':
            end = find_next(j_string, '"', 2, pos=sep)
            entry = j_string[:end + 1]
            name, pos_name = find_match_closure(entry, '"', '"', 0, sep)
            name = name[name.find('"')+1:name.rfind('"')]
            value, pos_value = find_match_closure(entry, '"', '"', sep)
            value = value[value.find('"') + 1:value.rfind('"')]
            start = end + 1
            json_dict[name] = value
        else:
            entry = j_string[j_string.find('"')+1:j_string.rfind('"', 0, sep)]
            text_sec, sec_end = find_match_closure(j_string, '{', '}', begin=sep)
            json_dict[entry] = parse_json(text_sec)
            start = sec_end
        sep = j_string.find(':', start)

    return json_dict


def collect_key(s_data, save=False):
    """Collect all keys from JSON and store in key.csv"""

    import os
    import json
    import csv

    def merge_list(my_list):

        def tu2lt(tpl):
            if type(tpl) is list or type(tpl) is tuple:
                return [tu2lt(cn) for cn in tpl]
            return tpl

        wrk_list = tu2lt(my_list)[:]

        nesting = False
        pos = 0
        for item in wrk_list:
            if type(item) is list:
                nesting = True
                break
            else:
                pos += 1

        exp_list = []
        if nesting:
            for item in wrk_list[pos]:
                if type(item) is str:
                    comb = wrk_list[pos - 1] + '.' + item
                    exp_list.append(comb)
                else:
                    exp_list.append(item)
        else:
            return wrk_list

        ret_list = wrk_list[:pos - 1] + exp_list + wrk_list[pos + 1:]
        ret_list = merge_list(ret_list)

        return ret_list

    if type(s_data) is list:
        data_file = s_data[:]
    else:
        s_data = os.path.join(os.getcwd(), 'nectec', s_data)
        data_file = []
        f = open(s_data, 'rt', encoding='utf-8')
        for line in f:
            data_file.append(json.loads(line))

    data = []
    for line in data_file:
        new_line = parse_key(line)
        new_line = merge_list(new_line)
        new_line.sort()
        dup = False
        for item in data:
            if item == new_line:
                dup = True
        if not dup:
            data.append(new_line)

    if save:
        with open(os.path.join(os.getcwd(), 'nectec', 'keys.csv'), 'w', newline='') as outFile:
            wr = csv.writer(outFile, dialect='excel')
            wr.writerows(data)

    return data


def parse_key(data):
    """Make a nested list of keys"""

    keys = list(data.keys())
    new_keys = []
    for key in keys:
        if type(data[key]) is dict:
            nest_key = [key, parse_key(data[key])]
            new_keys = new_keys + nest_key[:]
        else:
            new_keys.append(key)
    return new_keys


def get_text(f_path):

    import os
    import json
    import pickle

    def list_intersect(s_list, recure=False):

        if not recure:
            for item in s_list:
                if not (type(item) is list or type(item) is tuple):
                    return None
        if len(s_list) > 1:
            intersect = [val for val in s_list[0] if val in s_list[1]]
            new_list = [intersect] + s_list[2:]
            return list_intersect(new_list, True)
        else:
            return s_list[0]

    def get_nested(dict_data, args):
        if args and dict_data:
            element = args[0]
            if element:
                value = dict_data.get(element)
                return value if len(args) == 1 else get_nested(value, args[1:])

    def remove_non_unicode(text):
        """Remove all non-unicode and 4 bytes unicode characters."""
        import re

        re_pattern = re.compile(u'[^\u0000-\uD7FF\uE000-\uFFFF]', re.UNICODE)
        ret_text = re_pattern.sub('', text)

        return ret_text

    f_path = os.path.join(os.getcwd(), 'nectec', f_path)
    data_file = []
    f = open(f_path, 'rt', encoding='utf-8')
    for line in f:
        data_file.append(json.loads(line))
    f.close()

    keys = {}
    for key in list_intersect(collect_key(data_file)):
        temp = key.split('.')
        if temp == key:
            keys[key] = [key]
        else:
            keys[key] = temp
    keys_key = list(keys.keys())
    keys_key.sort()

    data_table = []
    for data in data_file:
        entry = {}
        for key in keys_key:
            entry[key] = remove_non_unicode(get_nested(data, keys[key]))
        data_table.append(entry)

    with open(os.path.join(os.getcwd(), 'nectec', 'job_ad_data.csv'), 'wt', encoding='utf-8') as outfile:
        for item in data_table:
            l_company = 'NA'
            l_title = item['title']
            l_url = item['url']
            l_desc = item['desc'].replace('\n', '.').replace('\t', '.')
            line = '`NA`,`' + l_title + '`,`' + l_url + '`,`' + l_desc + '`,\t\n'
            outfile.write(line)

    with open(os.path.join(os.getcwd(), 'nectec', 'job_ad_data.pickle'), 'wb') as pickfile:
        pickle.dump(data_table, pickfile)

    return data_table
