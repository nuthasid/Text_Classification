
class Tokenizer:

    def __init__(self, n_gram, stop_en=None, stop_th=None, keyword=None):

        import re
        import deepcut
        import os
        from nltk.tokenize import TreebankWordTokenizer
        from clean_text import CleanText

        self.cleaner = CleanText(stop_en=stop_en, stop_th=stop_th, keyword=keyword)
        self.test_text = 'ตัวอย่างความต้องการใช้ตัวอย่างความต้องการลีนุ๊กซ์การใช้ยากลำบาก'
        self.eng_tokenizer = TreebankWordTokenizer()
        self.n_gram = n_gram
        self.dp = deepcut

        self.pattern_sentence_collide = re.compile('[a-z][A-Z]]')
        self.pattern_thai_char = re.compile(u'[\u0e00-\u0e7f]')
        if keyword:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dict', keyword), 'rt', encoding='utf-8') as keyword_file:
                self.keyword = set([item for item in keyword_file.read().split('\n')])
        else:
            self.keyword = set([])

    def tokenizer(self, text=None, cleaning=False):

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

        if not text:
            return
        elif text == '-test':
            text = self.test_text

        if cleaning:
            text = self.cleaner.clean_text(text)
        text_split = text.split('|')

        first_pass = []
        for i, item in enumerate(text_split):
            if self.pattern_sentence_collide.search(item) and item not in self.keyword:
                c_text = self.pattern_sentence_collide.search(item)
                first_pass.extend([c_text.string[:c_text.span()[0]+1], c_text.string[c_text.span()[1]-1:]])
            else:
                first_pass.append(item)
        second_pass = []
        for i, chunk in enumerate(first_pass):
            if self.pattern_thai_char.search(chunk) and len(chunk) > 1:
                new_chunk = self.dp.tokenize(chunk)
                new_chunk = n_grams_compile(new_chunk, self.n_gram)
                second_pass.extend(new_chunk)
            else:
                second_pass.append(chunk.lower())

        return second_pass
