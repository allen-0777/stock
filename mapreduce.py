numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9]
squared = list(map(lambda x: x*2, numbers))
print(squared)  # [1, 4, 9, 16]
from functools import reduce
# numbers = [1, 2, 3, 4]
total = reduce(lambda x, y: x+y, numbers)
print(total)  # 10
