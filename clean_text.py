class CleanText:

    def __init__(self, stop_en=None, stop_th=None, keyword=None):

        import re
        import os
        from nltk.stem.snowball import EnglishStemmer

        self.pattern_thai_char = re.compile(u'[\u0e00-\u0e7f]')
        self.pattern_new_sentence = re.compile('\.[0-9]+(\)|\.) ')
        self.pattern_th_out = re.compile(u'[\u0e00-\u0e7f][^\u0e00-\u0e7f]')
        self.pattern_th_in = re.compile(u'[^\u0e00-\u0e7f][\u0e00-\u0e7f]')
        self.pattern_num_bullet = re.compile('^[0-9]+(\)|\.)*$')
        self.pattern_end_token = re.compile('^[a-zA-Z]+$')
        self.pattern_number = re.compile('\+*[0-9]+')
        self.pattern_phone_number = re.compile('[0-9]+-[0-9]+-[0-9]+')
        self.pattern_email = re.compile('[a-zA-Z._\-0-9]+@[a-zA-Z._\-0-9]+')
        self.pattern_url = re.compile('(https://|www.)[a-zA-Z0-9]+.[a-z]+[^\s]*')
        self.pattern_sentence_collide = re.compile('[a-z][A-Z]]')
        self.pattern_thai_name = re.compile(u'\u0e04\u0e38\u0e13\s*[\u0e00-\u0e7f]+\s+')
        self.charset = {}
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dict', 'charset'), 'rt') as charfile:
            for item in charfile.read().split('\n'):
                if len(item) < 4:
                    self.charset[item] = ord(item)
                else:
                    self.charset[chr(int(item, 16))] = int(item, 16)
        self.stemming = EnglishStemmer()

        if stop_en:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dict', stop_en), 'rt', encoding='utf-8') as stop_file:
                self.stop_en = set([item for item in stop_file.read().split('\n')])
        else:
            self.stop_en = set([])
        if stop_th:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dict', stop_th), 'rt', encoding='utf-8') as stop_file:
                self.stop_th = set([item for item in stop_file.read().split('\n')])
        else:
            self.stop_th = set([])
        if keyword:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dict', keyword), 'rt', encoding='utf-8') as keyword_file:
                self.keyword = set([item for item in keyword_file.read().split('\n')])
        else:
            self.keyword = set([])

    def clean_text(self, text):

        def validate_char(val_text):
            val_text = val_text.replace('&amp;', ' ')
            val_text = val_text.replace('&nbsp;', ' ')
            ret_text = ''
            for cha in val_text:
                try:
                    self.charset[cha]
                except KeyError:
                    ret_text += ' '
                else:
                    ret_text += cha
            while ret_text.find('  ') != -1:
                ret_text = ret_text.replace('  ', ' ')
            return ret_text

        def split_th_en(splt_text):
            insert_pos = []
            splt_text = splt_text[:]
            for pos, item in enumerate(splt_text[:-2]):
                if self.pattern_th_in.search(splt_text[pos:pos+2]) or self.pattern_th_out.search(splt_text[pos:pos+2]):
                    insert_pos.append(pos + 1)
            for pos in reversed(insert_pos):
                splt_text = splt_text[:pos] + ' ' + splt_text[pos:]
            return splt_text

        def remove_thai_stop(th_text):
            stop_pos = [[0, 0]]
            ## TH : do longest matching
            for j in range(len(th_text)-1):
                for k in range(j+1, len(th_text)):
                    if th_text[j:k] in self.stop_th:
                        # found keyword +++ instead of returning string - return positions that is
                        # i to j
                        if j <= stop_pos[-1][1]:
                            stop_pos[-1] = [stop_pos[-1][0], k]
                        else:
                            stop_pos.append([j, k])
                        break
            newstr = ''
            if len(stop_pos) == 1:
                newstr = th_text
            else:
                for j in range(len(stop_pos)-1):
                    newstr += th_text[stop_pos[j][1]:stop_pos[j+1][0]] + ' '
            return newstr

        text = text.replace(u'\u0e46', ' ')
        text = self.pattern_email.sub(' ', text)
        text = self.pattern_url.sub(' ', text)
        text = self.pattern_phone_number.sub(' ', text)
        text = self.pattern_thai_name.sub(' ', text)
        text = split_th_en(text)
        text = self.pattern_new_sentence.sub(' . ', text)
        text = text.replace('.', ' . ')
        text = validate_char(text)
        text = remove_thai_stop(text)
        text_split = text.split(' ')
        text_split = [item for item in text_split[:] if item not in self.stop_en
                      and not self.pattern_num_bullet.search(item)]
        text_split = [self.stemming.stem(item) if self.pattern_end_token.search(item) and
                                                  item not in self.keyword else item for item in text_split[:]]
        text = '|'.join(text_split)

        return text
