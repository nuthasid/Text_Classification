## manual classifier

import json
fileToTag = "block1"

filein = fileToTag+".json"
fileout = fileToTag+"_tagged.json"

fout = open(fileout,'w',encoding='utf-8')

with open(filein, encoding="utf-8") as fin:
    for line in fin:
        thisline = json.loads(line)
        print("TITLE : \n"+thisline['title'])
        print()
        print("DESCRIPTION : \n"+thisline['desc'])
        tag = input()
        thisline['tag'] = tag
        fout.write(json.dumps(thisline, ensure_ascii=False)+"\n")
fout.close()
