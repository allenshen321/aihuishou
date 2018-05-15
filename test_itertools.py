from itertools import product

a = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

b = ''
for each in a:
    if each != a[-1]:
        b += str(each) + ','
    else:
        b += str(each)
c = list(product(*eval(b)))
print(c)
print(len(c))
