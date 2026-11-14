# Demo 3: IndexError - loop goes one step too far.
fruits = ["apple", "banana", "mango"]
for i in range(len(fruits) + 1):
    print(i + 1, fruits[i])
