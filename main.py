# def main():
#     print("Hello from agora-ai-engine!")


# if __name__ == "__main__":
#     main()


from src.services.llm_service import ask_llm

if __name__ == "__main__":
    res = ask_llm("What is AI?")
    print(res)