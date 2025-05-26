import os
import time
import json
import openai
from datetime import datetime
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Set up the client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview",  # Use the latest available API version
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

# Define three different prompts to test
prompts = [
    {"role": "user", "content":  "What was first, egg or chicken"},

    {"role": "user", "content":  "Explain the concept of fenomenology in Hegelian philosophy."},

    {"role": "user", "content":  "Prepare a 3k usd PC with the best perfomance in 4k gaming."}
]


def log_usage(prompt_idx, prompt, response, metrics):

    with open("logs/usage.md", "a") as f:
        f.write(f"## Prompt {prompt_idx + 1}\n")
        f.write(f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")


        f.write("### Prompt\n")
        f.write(f"{prompt}\n\n")


        f.write("### Response\n")
        f.write(f"{response.choices[0].message.content}\n\n")


        f.write("### Metrics\n")
        f.write(f"- **Input Tokens:** {metrics['input_tokens']}\n")
        f.write(f"- **Output Tokens:** {metrics['output_tokens']}\n")
        f.write(f"- **Total Tokens:** {metrics['total_tokens']}\n")
        f.write(f"- **Cost:** ${metrics['cost']:.6f}\n")
        f.write(f"- **Token Efficiency Ratio:** {metrics['output_tokens'] / metrics['input_tokens']:.2f}\n\n")
        f.write("---\n\n")


def get_tokens_and_cost(response):

    usage = response.usage


    input_cost_per_token = 0.00003  # $0.03
    output_cost_per_token = 0.00006  # $0.06

    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    total_tokens = usage.total_tokens

    cost = (input_tokens * input_cost_per_token) + (output_tokens * output_cost_per_token)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost": cost
    }


def run_prompts():
    os.makedirs("logs", exist_ok=True)


    with open("logs/usage.md", "w") as f:
        f.write("# GPT-4o Usage Log\n\n")

    results = []

    for i, prompt in enumerate(prompts):
        print(f"Running prompt {i + 1}...")

        try:





            response = client.chat.completions.create(
                model=os.getenv("DEPLOYMENT_NAME"),
                messages=[prompt], # Still expects an array of messages, but i need to prompt one by one to track the cost
                temperature=0.7,
                max_tokens=1000
            )


            metrics = get_tokens_and_cost(response)


            log_usage(i, prompt, response, metrics)

            results.append({
                "prompt_idx": i,
                "metrics": metrics
            })


            time.sleep(1)

        except Exception as e:
            print(f"Error with prompt {i + 1}: {str(e)}")


    most_efficient_idx = -1
    best_efficiency = 0

    for result in results:
        metrics = result["metrics"]
        efficiency = metrics["output_tokens"] / metrics["input_tokens"] if metrics["input_tokens"] > 0 else 0

        if efficiency > best_efficiency:
            best_efficiency = efficiency
            most_efficient_idx = result["prompt_idx"]


    with open("logs/usage.md", "a") as f:
        f.write("## Analysis\n\n")
        f.write(
            f"The most efficient prompt was **Prompt {most_efficient_idx + 1}** with an output-to-input token ratio of {best_efficiency:.2f}.\n")


if __name__ == "__main__":
    run_prompts()
    print("Completed running all prompts. Results logged to /logs/usage.md")