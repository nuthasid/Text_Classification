import time
from tokenizer import Tokenizer

text = 'ที่อีกกลุ่มคือพรรคพรรคตั้งใหม่ซึ่งตรงนี้ไม่เคยมีผลงานทาง'
text += text
text += text
text += text
text += text
text += text
text += text
text += text
text += text
text += text
tokenize = Tokenizer(1)

t1 = time.time()
print(len(tokenize.tokenizer(text)))
print(time.time()-t1)
