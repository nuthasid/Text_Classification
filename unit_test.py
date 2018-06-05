def parse_json(j_string):

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
        """Return an element in 'sub' which occurs first in string 'text' beginning from position 'pos'."""
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


def test_parse(f_name='text_json_full.txt'):

    import os

    f_path = os.path.join(os.getcwd(), 'data', f_name)

    with open(f_path, 'rt', encoding='utf-8') as f:
        mtxt = f.read()

    print(parse_json(mtxt))


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


def merge_list(my_list=('a', 'b', ('c', 'd', ('0', '1', '2')), 'z')):

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
                comb = wrk_list[pos-1] + '.' + item
                exp_list.append(comb)
            else:
                exp_list.append(item)
    else:
        return wrk_list

    ret_list = wrk_list[:pos - 1] + exp_list + wrk_list[pos + 1:]
    ret_list = merge_list(ret_list)

    return ret_list

def remove_non_unicode(text):
    """Remove all non-unicode and 4 bytes unicode characters."""
    import re

    re_pattern = re.compile(u'[^\u0000-\uD7FF\uE000-\uFFFF]', re.UNICODE)
    ret_text = re_pattern.sub('', text)

    return ret_text

def run_wf():
    import os
    from word_counting import word_frequency as wf
    wf(save='20180312')
    os.system('shutdown -s')

