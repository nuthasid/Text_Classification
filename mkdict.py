
def main(exc_list, wordlist_en='customdict_en.txt', wordlost_th='customdict_th.txt', typos='misspelled.txt'):

    import os

    exc_path = os.path.join(os.getcwd(), 'dict', exc_list)
    en_path = os.path.join(os.getcwd(), 'dict', wordlist_en)
    th_path = os.path.join(os.getcwd(), 'dict', wordlost_th)
    mis_path = os.path.join(os.getcwd(), 'dict', typos)
    print('Enter "/" to add to dictionary, "\'" to put in misspelled dict, Otherwise "ENTER"')

    words = []
    with open(exc_path, 'rt', encoding='utf-8') as f:
        for line in f.readlines():
            words.append(line.split('\t'))

    total = len(words)
    counter = 0
    for word in words:
        print('\n'*14 + 'Completed ' + str(counter) + ' out of ' + str(total))
        print(word[0] + '\t' + word[1] + '\n'*14)
        inp = input()
        if inp == '/':
            if ord(word[0][0]) in range(3584, 3712):
                with open(th_path, 'at', encoding='utf-8') as thf:
                    thf.write(word[0] + '\n')
            else:
                with open(en_path, 'at', encoding='utf-8') as enf:
                    enf.write(word[0] + '\n')
        elif inp == "'":
            with open(mis_path, 'at', encoding='utf-8') as mis:
                mis.write(word[0] + '\n')
        else:
            pass
        counter += 1


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
