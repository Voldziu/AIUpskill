import json
import random
import sys
from openai import AzureOpenAI


class QuizGame:
    def __init__(self, api_key=None, endpoint=None, deployment_name=None):

        self.client = None
        if api_key and endpoint and deployment_name:
            try:
                self.client = AzureOpenAI(
                    api_key=api_key,
                    api_version="2024-12-01-preview",
                    azure_endpoint=endpoint
                )
                self.deployment_name = deployment_name
            except Exception as e:
                print(f"Warning: Could not initialize AI client: {e}")
                print("Falling back to static questions...")

        self.score = 0
        self.total_questions = 0
        self.categories = [
            "Science", "History", "Geography", "Literature",
            "Mathematics", "Technology", "Sports", "Art"
        ]

        # If api fails, use static questions
        self.fallback_questions = [
            {
                "question": "What is the capital of France?",
                "options": ["London", "Berlin", "Paris", "Madrid"],
                "correct": 2,
                "category": "Geography"
            },
            {
                "question": "Who wrote 'Romeo and Juliet'?",
                "options": ["Charles Dickens", "William Shakespeare", "Jane Austen", "Mark Twain"],
                "correct": 1,
                "category": "Literature"
            },
            {
                "question": "What is 2 + 2?",
                "options": ["3", "4", "5", "6"],
                "correct": 1,
                "category": "Mathematics"
            }
        ]

    def load_quiz_prompt(self):

        try:
            with open("prompts/best.txt", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(
                "Prompt file not found at 'prompts/best.txt'. "
                "Please create it using --setup option first."
            )

    def generate_question(self, category):
        if not self.client:
            return random.choice(self.fallback_questions)

        try:
            prompt = self.load_quiz_prompt()
            user_prompt = f"Generate a {category} question following the format specified."

            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=300
            )


            content = response.choices[0].message.content.strip()

            print(f"AI Response: {content}")
            # A bit of cleanup
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            # Expecting json format, so try to parse it as if it is
            question_data = json.loads(content)
            question_data["category"] = category
            return question_data

        except Exception as e:
            print(f"Error generating question: {e}")
            print("Using fallback question...")
            return random.choice(self.fallback_questions)

    def ask_question(self, question_data):

        print(f"\n--- Category: {question_data['category']} ---")
        print(f"Question: {question_data['question']}\n")

        for i, option in enumerate(question_data['options']):
            print(f"{i + 1}. {option}")

        while True: # while true loop until answer is valid [ in (1,2,3,4)]
            try:
                answer = input("\nYour answer (1-4): ").strip()
                if answer in ['1', '2', '3', '4']:
                    return int(answer) - 1 #Indexing :)
                else:
                    print("Please enter 1, 2, 3, or 4")
            except KeyboardInterrupt:
                print("\n\nGame interrupted. Thanks for playing!")
                sys.exit(0)
            except EOFError:
                print("\n\nGame ended. Thanks for playing!")
                sys.exit(0)

    def check_answer(self, question_data, user_answer):

        correct_idx = question_data['correct'] # remember, this is 0-indexed
        correct_answer = question_data['options'][correct_idx]
        user_answer_text = question_data['options'][user_answer]

        if user_answer == correct_idx:
            print(f"✅ Correct! The answer is: {correct_answer}")
            if 'explanation' in question_data:
                print(f"💡 {question_data['explanation']}")
            self.score += 1
        else:
            print(f"❌ Wrong! You answered: {user_answer_text}")
            print(f"✅ The correct answer is: {correct_answer}")
            if 'explanation' in question_data:
                print(f"💡 {question_data['explanation']}")

        self.total_questions += 1

    def play_game(self, num_questions, category=None):
        """Main game loop"""
        print("🧠 Welcome to the AI-Powered Quiz Game! 🧠")
        print(f"You'll answer {num_questions} questions.")

        if category:
            print(f"Category: {category}")
            categories_to_use = [category] * num_questions
        else:
            print("Categories: Mixed")
            categories_to_use = [random.choice(self.categories) for _ in range(num_questions)]

        print("\nLet's begin!\n" + "=" * 50)

        for i in range(num_questions):
            print(f"\nQuestion {i + 1}/{num_questions}")

            current_category = categories_to_use[i]
            question_data = self.generate_question(current_category)

            user_answer = self.ask_question(question_data)
            self.check_answer(question_data, user_answer)

            if i < num_questions - 1:
                input("\nPress Enter to continue...")

        # Game summary
        print("\n" + "=" * 50)
        print("🎯 GAME OVER! 🎯")
        print(f"Final Score: {self.score}/{self.total_questions}")

        percentage = (self.score / self.total_questions) * 100
        print(f"Percentage: {percentage:.1f}%")

        if percentage >= 80:
            print("🏆 Excellent work! You're a quiz master!")
        elif percentage >= 60:
            print("👍 Good job! Well done!")
        elif percentage >= 40:
            print("📚 Not bad, but there's room for improvement!")
        else:
            print("💪 Keep studying and try again!")