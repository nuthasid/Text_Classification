
def levenshtein(word1, word2):
    """
        Return minimum edit distance between word1 and word2.
    """

    def call_counter(func):
        def helper(*args, **kwargs):
            helper.calls += 1
            return func(*args, **kwargs)

        helper.calls = 0
        helper.__name__ = func.__name__
        return helper

    memo = {}

    @call_counter
    def leven(s, t):
        if s == "":
            return len(t)
        if t == "":
            return len(s)
        cost = 0 if s[-1] == t[-1] else 1

        i1 = (s[:-1], t)
        if not i1 in memo:
            memo[i1] = leven(*i1)
        i2 = (s, t[:-1])
        if not i2 in memo:
            memo[i2] = leven(*i2)
        i3 = (s[:-1], t[:-1])
        if not i3 in memo:
            memo[i3] = leven(*i3)
        res = min([memo[i1] + 1, memo[i2] + 1, memo[i3] + cost])
        return res

    return leven(word1, word2)


def edu_tokenizer(doc):
    """
    :param doc: string document containing Thai text
    :return: a list of word tokens tokenized using tltk word segmentation
    """

    from tltk import segment

    return segment(doc).replace('<u/>', '|').replace('|<s/>|', '|').split('|')
