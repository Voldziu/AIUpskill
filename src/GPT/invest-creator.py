import os
import json
import argparse
from datetime import datetime
from openai import AzureOpenAI
from dotenv import load_dotenv


load_dotenv()


class UserStoryGenerator:
    def __init__(self):

        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-12-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment = os.getenv("DEPLOYMENT_NAME")

    def create_user_n_stories_prompt(self,num_stories, domain ="e-commerce shop"):


        json_example= '''{
        "stories": [
            {
        "id": "US001",
              "title": "Brief descriptive title",
              "story": "As a [user type], I want [goal] so that [benefit]",
              "business_value": "Clear explanation of business value",
              "acceptance_criteria": [
                "Given [context], when [action], then [expected result]",
                "Another clear acceptance criterion",
                "..."
              ],
              "invest_validation": {
        "independent": "Explanation of how this story is independent",
                "negotiable": "What aspects can be negotiated",
                "valuable": "Business value provided",
                "estimable": "Why this can be estimated",
                "small": "How this fits in a sprint",
                "testable": "How this can be tested"
              }
            }
          ]
        }'''

        return f"""You are a senior Product Owner and Agile expert specializing in creating high-quality user stories that follow INVEST criteria.

        INVEST CRITERIA REQUIREMENTS:
        - Independent: Stories can be developed independently without dependencies on other stories
        - Negotiable: Details can be discussed and refined, not overly prescriptive
        - Valuable: Provides clear business value to users or stakeholders
        - Estimable: Contains enough detail for development team to estimate effort
        - Small: Can be completed within a single sprint (1-2 weeks)
        - Testable: Has clear acceptance criteria that can be verified

        TASK: Generate {num_stories} distinct user stories for a {domain}. Each story should:

        1. Follow the format: "As a [user type], I want [goal] so that [benefit]"
        2. Include 3-5 specific acceptance criteria using Given/When/Then format where appropriate
        3. Target different aspects of an application (e.g., user interface, backend functionality, data processing)
        4. Be realistic and implementable within a sprint
        5. Provide clear business value

        OUTPUT FORMAT (JSON):
        {json_example}
        

        Focus on creating stories that a real development team would work on for a {domain}, avoiding overly complex or trivial examples."""

    def generate_user_stories(self,num_stories,domain):

        try:
            prompt = self.create_user_n_stories_prompt(num_stories,domain)


            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000 # If num_stories is 10, this would need more tokens.
            )
            print(response)

            content = response.choices[0].message.content.strip()


            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()

            return json.loads(content)

        except Exception as e:
            print(f"Error generating user stories: {e}")
            return None

    def format_markdown_output(self, stories_data,domain):
        """Format the stories as markdown for the backlog file"""
        markdown = f"""# Sprint 1 Backlog

**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Generated using:** GPT-4o with INVEST Criteria
**Domain:** {domain.title()}

## Overview
This backlog contains three user stories that follow INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable) and include comprehensive acceptance criteria for Sprint 1 development.

---

"""

        for i, story in enumerate(stories_data["stories"], 1):
            markdown += f"""## {story['id']}: {story['title']}

### User Story
{story['story']}

### Business Value
{story['business_value']}

### Acceptance Criteria
"""
            for j, criteria in enumerate(story['acceptance_criteria'], 1):
                markdown += f"{j}. {criteria}\n"

            markdown += f"""
### INVEST Validation
- **Independent:** {story['invest_validation']['independent']}
- **Negotiable:** {story['invest_validation']['negotiable']}
- **Valuable:** {story['invest_validation']['valuable']}
- **Estimable:** {story['invest_validation']['estimable']}
- **Small:** {story['invest_validation']['small']}
- **Testable:** {story['invest_validation']['testable']}

### Story Points
*To be estimated by the development team during planning poker*

### Priority
*To be determined by Product Owner*

---

"""

        markdown += """## Sprint Planning Notes
- All stories follow INVEST criteria
- Acceptance criteria use Given/When/Then format where applicable
- Stories are designed to be completed within a 2-week sprint
- Each story provides measurable business value
- Stories are independent and can be developed in any order
- Priority and story points will be finalized during sprint planning


*Generated using INVEST criteria best practices and current Scrum methodologies*
"""

        return markdown

    def create_backlog_file(self, num_stories, domain,output_filename):

        print("🚀 Generating INVEST user stories using GPT-4o...")


        stories_data = self.generate_user_stories(num_stories,domain)
        if not stories_data:
            print("Failed to generate user stories")
            return False

        # Create directory if it doesn't exist
        os.makedirs("backlog", exist_ok=True)

        # Format as markdown
        markdown_content = self.format_markdown_output(stories_data,domain)

        output_path = f"backlog/{output_filename}"

        # Write to file
        with open(output_path, "w") as f:
            f.write(markdown_content)

        print("✅ User stories generated and saved to /backlog/sprint1.md")
        print("\n📋 Generated Stories:")
        for story in stories_data["stories"]:
            print(f"  • {story['id']}: {story['title']}")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="SCRUM User Story Generator using GPT-4o",
    )

    parser.add_argument(
        "-n", "--num-stories",
        type=int,
        default=5,
        help="Number of stories to generate (default: 5)"
    )

    parser.add_argument(
        "-d", "--domain",
        default="modern software application",
        help="Application domain/type (default: 'modern software application')"
    )

    parser.add_argument(
        "--output",
        default="sprint1.md",
        help="Output filename in backlog/ directory (default: sprint1.md)"
    )

    args = parser.parse_args()

    num_stories = args.num_stories
    domain = args.domain
    output = args.output


    generator = UserStoryGenerator()

    success = generator.create_backlog_file(num_stories=num_stories,domain=domain, output_filename=output)

    if success:
        print("✅ User stories generated successfully! Check /backlog/sprint1.md for details.")
    else:
        print("❌ Failed to generate user stories. Please check your configuration.")


if __name__ == "__main__":
    main()