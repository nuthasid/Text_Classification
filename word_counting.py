
def word_frequency(f_path='job_ad_data.pickle', save=None, start_pos=None, end_pos=None):

    import os
    import pickle
    import csv
    import time
    from tokenizer import Tokenizer

    def remove_white_space(in_text):

        out_text = in_text.replace('\t', ' ').replace('\n', ' ')
        while not out_text.find('  ') == -1:
            out_text = out_text.replace('  ', ' ')

        return out_text

    tokenizer = Tokenizer(4)

    with open(os.path.join(os.getcwd(), 'nectec', f_path), 'rb') as pf:
        dict_data = pickle.load(pf, encoding='utf-8')

    token_tally = {}
    document_length = []
    token_list = []
    special_char = ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+', '?', '/', '\\', '"', ':', ';',
                    'ๆ', ',', '?', '(', ')', '<', '>', ',', ' ', "'"]
    num_sample = str(len(dict_data))
    counter = 0
    print('============Start tokenization============')
    elaspe = time.time()
    for item in dict_data[start_pos:end_pos]:
        counter += 1
        text = remove_white_space(item['desc'])
        print('Tokenizing ' + str(counter) + ' of ' + num_sample + ' sample.')
        tokens = tokenizer.tokenizer(text)
        token_list.append(tokens)
        words = [token for token in tokens if token not in special_char]
        document_length.append([len(words)])
        for token in tokens:
            try:
                token_tally[token] += 1
            except KeyError:
                token_tally[token] = 1
    print('============Finish tokenization============')

    if save:

        with open(os.path.join(os.getcwd(), 'nectec', 'token_list_' + save + '.pickle'), 'wb') as token_file:
            pickle.dump(token_list, token_file, pickle.HIGHEST_PROTOCOL)
        with open(os.path.join(os.getcwd(), 'nectec', 'token_tally_' + save + '.txt'), 'wt', encoding='utf-8',
                  newline='') as ttf:
            outfile = csv.writer(ttf, delimiter='\t', dialect='excel')
            for word in token_tally.keys():
                outfile.writerow([word, token_tally[word]])
        with open(os.path.join(os.getcwd(), 'nectec', 'doc_length_' + save + '.txt'), 'wt', encoding='utf-8',
                  newline='') as ttf:
            outfile = csv.writer(ttf, delimiter=',', dialect='excel')
            outfile.writerows(document_length)

    elaspe = time.time() - elaspe

    return token_tally, document_length, elaspe


def concat_tally(f_list, outfile):

    import os
    import csv

    def open_csv(f_name):
        ret_list = {}
        with open(f_name, 'r', encoding='utf-8') as t_file:
            csv_file = csv.reader(t_file, delimiter='\t')
            for line in csv_file:
                if line:
                    ret_list[line[0]] = int(line[1])
        return ret_list

    tally = open_csv(os.path.join(os.getcwd(), 'nectec', f_list[0]))
    for f in f_list[1:]:
        new_tally = open_csv(os.path.join(os.getcwd(), 'nectec', f))
        for token in new_tally.keys():
            try:
                tally[token] += new_tally[token]
            except KeyError:
                tally[token] = new_tally[token]
    with open(os.path.join(os.getcwd(), 'nectec', outfile), 'wt', encoding='utf-8', newline='') as ttf:
        outfile = csv.writer(ttf, delimiter='\t', dialect='excel')
        for word in tally.keys():
            outfile.writerow([word, tally[word]])
    return tally
