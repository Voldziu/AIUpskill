
import argparse
import os
from QuizGame import QuizGame
from dotenv import load_dotenv
def create_directories():

    os.makedirs("prompts", exist_ok=True)


def create_quiz_prompt():

    create_directories() # If needed

    prompt_content =\
    \
    """You are QuizMaster, an expert quiz generator who creates engaging and educational multiple-choice questions.

    Your task is to generate ONE high-quality  question based on the given category.
    
    REQUIREMENTS:
    1. Create exactly 4 answer options (A, B, C, D)
    2. Ensure only ONE answer is clearly and definitively correct
    3. Make incorrect options plausible but clearly wrong to someone with knowledge
    4. Question should be appropriate difficulty - challenging but fair
    5. Include a brief explanation for why the correct answer is right
    
    OUTPUT FORMAT (JSON):
    {
      "question": "Your question text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": 2,
      "explanation": "Brief explanation of why this answer is correct"
    }
    
    QUALITY GUIDELINES:
    - Questions should test knowledge, not trick the user
    - Avoid ambiguous wording
    - Make sure the correct answer is factually accurate
    - Keep questions concise but clear
    - For science/math: Include specific facts or calculations
    - For history: Focus on significant events, dates, or figures  
    - For geography: Test knowledge of locations, capitals, features
    - For literature: Cover authors, works, literary devices
    - For technology: Current and foundational concepts
    - For arts: Famous works, artists, movements, techniques
    
    Generate educational content that helps users learn while being challenged."""

    with open("prompts/best.txt", "w") as f:
        f.write(prompt_content)

    print("✅ Quiz-bot prompt saved to /prompts/best.txt")


def main():
    """Parse arguments """
    parser = argparse.ArgumentParser(
        description="AI Game: QuizBot"
    )

    parser.add_argument(
        "-n", "--num-questions",
        type=int,
        default=5,
        help="Number of questions to ask (default: 5)"
    )

    parser.add_argument(
        "-c", "--category",
        choices=["Science", "History", "Geography", "Literature", "Mathematics", "Technology", "Sports", "Art"],
        help="Specific category for all questions (default: mix of all categories)"
    )

    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Create the quiz-bot prompt file and exit"
    )

    parser.add_argument(
        "--api-key",
        help="Azure OpenAI API key (or set AZURE_OPENAI_API_KEY env var)"
    )

    parser.add_argument(
        "--endpoint",
        help="Azure OpenAI endpoint (or set AZURE_OPENAI_ENDPOINT env var)"
    )

    parser.add_argument(
        "--deployment",
        help="Azure OpenAI deployment name (or set DEPLOYMENT_NAME env var)"
    )

    args = parser.parse_args()


    if args.setup_only:
        create_quiz_prompt()
        return


    api_key =  os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = args.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = args.deployment or os.getenv("DEPLOYMENT_NAME")

    print(api_key, endpoint, deployment_name)


    game = QuizGame(api_key=api_key, endpoint=endpoint, deployment_name=deployment_name)

    try:
        game.play_game(args.num_questions, args.category)
    except KeyboardInterrupt:
        print("\n\nThanks for playing! 👋")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please check your configuration and try again.")


if __name__ == "__main__":
    load_dotenv()
    main()