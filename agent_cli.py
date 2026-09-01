from agent import LilpaAgent


def main() -> None:
    agent = LilpaAgent()

    print("Lilpa Agent started. Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        answer = agent.reply("cli", "User", user_input)
        print(f"Lilpa: {answer}")


if __name__ == "__main__":
    main()
