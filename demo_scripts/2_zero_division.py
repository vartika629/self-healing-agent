# Demo 2: ZeroDivisionError - average of an empty list.
def average(numbers):
    return sum(numbers) / len(numbers)

marks = {"Asha": [78, 85, 91], "Rohan": []}
for student, scores in marks.items():
    print(student, "average:", average(scores))
