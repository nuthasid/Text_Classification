
def main(exc_list, wordlist_en='wordlist_en.txt', wordlost_th='wordlist_th.txt', typos='misspelled.txt'):

    import os

    exc_path = os.path.join(os.getcwd(), 'dict', exc_list)
    en_path = os.path.join(os.getcwd(), 'dict', wordlist_en)
    th_path = os.path.join(os.getcwd(), 'dict', wordlost_th)
    mis_path = os.path.join(os.getcwd(), 'dict', typos)
    print('Enter "/" to add to dictionary, otherwise just hit ENTER')

    words = []
    with open(exc_path, 'rt', encoding='utf-8') as f:
        for line in f.readlines():
            words.append(line)

    total = len(words)
    counter = 0
    for word in words:
        print('\n'*10 + 'Completed ' + str(counter) + ' out of ' + str(total) + '\t'*3 + word + '\n'*10)
        inp = input()
        if inp == '/':
            if ord(word[0]) in range(3584, 3712):
                with open(th_path, 'at', encoding='utf-8') as thf:
                    thf.write(word + '\n')
            else:
                with open(en_path, 'at', encoding='utf-8') as enf:
                    enf.write(word + '\n')
        else:
            with open(mis_path, 'at', encoding='utf-8') as mis:
                mis.write(word + '\n')
        counter += 1


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
