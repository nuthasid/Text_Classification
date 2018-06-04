
class Tokenizer:

    def __init__(self, n_gram, en_stop=None, th_stop=None):

        import re
        import deepcut
        from nltk.tokenize import TreebankWordTokenizer

        self.test_text = 'This is a test text. นี่เป็นตัวอย่าง ข้อความtest ใน Python 3.6.'
        self.pattern = re.compile(u'[\u0e01-\u0e2e]')
        self.eng_tokenizer = TreebankWordTokenizer()
        self.n_gram = n_gram
        self.dp = deepcut
        if en_stop:
            with open('\\dict\\' + en_stop, 'rt', encoding='utf-8') as stop_file:
                self.en_stop = set([item for item in stop_file.read().split('\n')])
        else:
            self.en_stop = set([])

    def tokenizer(self, text=None):

        def n_gram_compile(tokens, n):

            tokens = tokens[:]
            n_tokens = []
            if n <= 1:
                return tokens
            for j, token in enumerate(tokens[:-(n - 1)]):
                new_token = ''
                for word in tokens[j:j + n]:
                    if self.pattern.search(word) and len(word) > 1:
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

        if text == '-test':
            text = self.test_text

        in_text = text.replace('.', ' . ').replace(u'\xa0', ' ').replace('  ', ' ')
        first_pass = self.eng_tokenizer.tokenize(in_text)
        first_pass = [item for item in first_pass[:] if item not in self.en_stop]
        second_pass = []
        for i, chunk in enumerate(first_pass):
            if self.pattern.search(chunk) and len(chunk) > 1:
                new_chunk = self.dp.tokenize(chunk)
                second_pass.extend(new_chunk)
            else:
                second_pass.append(chunk.lower())

        second_pass = n_grams_compile(second_pass, self.n_gram)

        return second_pass
