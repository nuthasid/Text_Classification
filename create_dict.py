
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

    def clean_text(self, text, stemming=True):

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
                for k in range(j+1, min(len(th_text), j+1+36)):
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

        #import os
        import time

        #pid = os.getpid()

        #start = time.time()

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
        if stemming:
            text_split = [self.stemming.stem(item) if self.pattern_end_token.search(item) and
                                                      item not in self.keyword else item for item in text_split[:]]
        text = '|'.join(text_split)

        #print('process: ', pid, ' time:', time.time() - start, ' len:', len(text))

        return text


class CreateDict:

    def __init__(self, tokenizer, n_gram=1, processes=8, tokenize_processes=8, stop_en=None, stop_th=None, keyword=None, th_wordlist=None,
                 en_wordlist=None):

        from tokenizer import Tokenizer
        import json
        import os

        Clean_Text = CleanText(stop_en=stop_en, stop_th=stop_th, keyword=keyword)
        self.clean_text = Clean_Text.clean_text
        TKN = Tokenizer(tokenizer=tokenizer, n_gram=n_gram, stop_en=stop_en, stop_th=stop_th, keyword=keyword)
        self.tkn = TKN.tokenizer
        self.processes = processes
        self.token_processes = tokenize_processes
        self.n_gram = n_gram
        if th_wordlist:
            with open(os.path.join(os.getcwd(), '..', 'dict', th_wordlist), 'rt', encoding='utf-8') as f:
                self.wordlist_th = json.load(f)
        else:
            self.wordlist_th = None
        if en_wordlist:
            with open(os.path.join(os.getcwd(), '..', 'dict', en_wordlist), 'rt', encoding='utf-8') as f:
                self.wordlist_en = json.load(f)
        else:
            self.wordlist_en = None

    def compile_dict(self, docs):

        import pathos.multiprocessing as mp
        import time

        start = time.time()

        pool = mp.ProcessPool(nodes=self.processes)
        cleaned = pool.amap(self.clean_text, docs)

        print('pool done:', time.time() - start)

        cleaned = cleaned.get()

        print('get done:', time.time() - start)

        dicts = [self.tkn(doc, False) for doc in cleaned]

        print('tokenize:', time.time() - start)

        return dicts

    def create_dict(self, docs, match_suggest=False):
        """
            Use tokenizer such as deepcut to get a list of actual words being used in job posting.
            Compare the list with dictionary and collect words that don't appear in the dictionary.
            If the words are misspelled, then mark as possible typos.
            If the words are correctly spelled but are not included in the dictionary, add the word to the dictionary.
        """

        import pathos.multiprocessing as mp
        from nlp_lib import levenshtein as lv
        import os
        import time
        import copy

        def levenshtein(word, wl):
            """
            Take a word, find closest word in dict according to levenshtein distance.
            Return closest word and corresponding minimum edits. (original_word, closest_match, edits)
            """

            start = time.time()
            print('Start: ', os.getpid(), word)

            min_edit = len(word)*2
            match = None

            for item in wl:
                edit = lv(word, item)
                if edit < min_edit:
                    min_edit = edit
                    match = item

            print('Stop: ', os.getpid(), word, ': ', str(time.time()-start))

            return (word, match, item)

        def find_matching(word):

            if ord(word[0]) in range(3584, 3712):
                current_wl = self.wordlist_th
            else:
                current_wl = self.wordlist_en
            if word in current_wl:
                return (word, word, 0)
            else:
                return (word, word, 1)

        def clean_text(doc):
            return self.clean_text(doc, False)

        if self.wordlist_th and self.wordlist_en:
            pass
        else:
            return None

        start = time.time()

        pool = mp.ProcessPool(nodes=self.processes)
        docs = pool.amap(clean_text, docs)
        docs = docs.get()
        print('Finish cleaning text - time: ', str(time.time()-start))
        if self.token_processes == 1:
        #    tokens = [self.tkn(doc) for doc in docs]
            tokens = []
            for doc in docs:
                doc = doc.replace('|', ' ')
                token = self.tkn(doc)
                tokens.append(token)
        else:
            pool = mp.ProcessPool(nodes=self.processes)
            tokens = pool.amap(self.tkn, docs)
            tokens = tokens.get()
        print('Finish tokenization - time: ', str(time.time()-start))
        temp = copy.deepcopy(tokens)
        tokens = []
        for item in temp:
            tokens.extend(item)
        tokens = [item.lower() for item in tokens if item != '']
        tokens.sort()
        temp = copy.deepcopy(tokens)
        tokens = set(tokens)
        dicts = {}
        for token in tokens:
            dicts[token] = 0
        for doc in temp:
            for token in doc:
                if token in dicts:
                    dicts[token] += 1
        print('Finish compile list - time: ', str(time.time()-start))
        pool = mp.ProcessPool(nodes=self.processes)
        wordlist = pool.amap(find_matching, tokens)
        wordlist = wordlist.get()
        dict_in = {}
        dict_out = {}
        for word in wordlist:
            if word[2] == 0:
                dict_in[word[0]] = dicts[word[0]]
            else:
                dict_out[word[0]] = dicts[word[0]]
        return dict_in, dict_out, temp
