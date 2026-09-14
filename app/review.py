print("AI Feedback Review")
print("------------------")

with open("app/feedback.txt", "r", encoding="utf-8") as file:
    feedbacks = file.readlines()

for feedback in feedbacks:
    print(feedback)