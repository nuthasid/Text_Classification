
class Tokenizer:

    def __init__(self, n_gram, stop=None, keyword=None):

        import re
        import deepcut
        import os
        from nltk.tokenize import TreebankWordTokenizer
        from nltk.stem.snowball import EnglishStemmer

        self.test_text = 'This is a test text. นี่เป็นตัวอย่าง ข้อความtesting ใน Python 3.6. ทดสอบtest.2) ทดสอบ3.'
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
        with open(os.path.join(os.getcwd(), 'dict', 'charset'), 'rt') as charfile:
            for item in charfile.read().split('\n'):
                if len(item) < 4:
                    self.charset[item] = ord(item)
                else:
                    self.charset[chr(int(item, 16))] = int(item, 16)
        self.eng_tokenizer = TreebankWordTokenizer()
        self.stemming = EnglishStemmer()
        self.n_gram = n_gram
        self.dp = deepcut
        if stop:
            with open(os.path.join(os.getcwd(), 'dict', stop), 'rt', encoding='utf-8') as stop_file:
                self.stop = set([item for item in stop_file.read().split('\n')])
        else:
            self.stop = set([])
        if keyword:
            with open(os.path.join(os.getcwd(), 'dict', keyword), 'rt', encoding='utf-8') as keyword_file:
                self.keyword = set([item for item in keyword_file.read().split('\n')])
        else:
            self.keyword = set([])

    def tokenizer(self, text=None):

        def n_gram_compile(tokens, n):

            tokens = tokens[:]
            n_tokens = []
            if n <= 1:
                return tokens
            for j, token in enumerate(tokens[:-(n - 1)]):
                new_token = ''
                for word in tokens[j:j + n]:
                    if self.pattern_thai_char.search(word) and len(word) > 1:
                        new_token += word
                    else:
                        new_token = ''
                        break
                if new_token:
                    n_tokens.extend([new_token])
            return n_tokens

        def n_grams_compile(tokens, n):

            if n < 2:
                return tokens
            n_tokens = []
            for j in range(2, n + 1):
                n_tokens.extend(n_gram_compile(tokens, j))
            n_tokens = tokens + n_tokens
            return n_tokens

        def validate_char(val_text):
            val_text = val_text.replace('&amp;', ' ')
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

        if text == '-test':
            text = self.test_text

        text = self.pattern_email.sub(' ', text)
        text = self.pattern_url.sub(' ', text)
        text = self.pattern_phone_number.sub(' ', text)
        text = self.pattern_thai_name.sub(' ', text)
        text = split_th_en(text)
        text = self.pattern_new_sentence.sub(' . ', text)
        text = text.replace('.', ' . ')
        text = validate_char(text)
        text_split = text.split(' ')
        text_split = [item for item in text_split[:] if item not in self.stop
                      and not self.pattern_num_bullet.search(item)]
        text_split = [self.stemming.stem(item) if self.pattern_end_token.search(item) and
                      item not in self.keyword else item for item in text_split[:]]

        first_pass = []
        for i, item in text_split:
            if self.pattern_sentence_collide.search(item) and item not in self.keyword:
                c_text = self.pattern_sentence_collide.search(item)
                first_pass.extend([c_text.string[:c_text.span()[0]+1], c_text.string[c_text.span()[1]-1:]])
            else:
                first_pass.append(item)
        second_pass = []
        for i, chunk in enumerate(first_pass):
            if self.pattern_thai_char.search(chunk) and len(chunk) > 1:
                new_chunk = self.dp.tokenize(chunk)
                second_pass.extend(new_chunk)
            else:
                second_pass.append(chunk.lower())

        second_pass = n_grams_compile(second_pass, self.n_gram)

        token_list = list(set(second_pass))

        return token_list
