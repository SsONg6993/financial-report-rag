from src.ask_intent import AskIntent, route_ask


def test_general_medical_ai_question_does_not_select_company():
    route = route_ask("How do you think medical AI will develop in the future?")
    assert route.intent is AskIntent.GENERAL
    assert route.ticker is None


def test_financial_and_portfolio_questions_route_with_explicit_context():
    financial = route_ask("What changed in AAPL's latest quarter?")
    portfolio = route_ask("Why did Berkshire reduce AAPL?")
    assert financial.intent is AskIntent.FINANCIAL_RESEARCH
    assert financial.ticker == "AAPL"
    assert portfolio.intent is AskIntent.PORTFOLIO_ANALYSIS
    assert portfolio.ticker == "AAPL"


def test_research_mode_rejects_context_free_general_question():
    route = route_ask("Explain the future of medical AI", mode="research")
    assert route.intent is AskIntent.UNSUPPORTED
    assert route.ticker is None


def test_current_public_information_and_account_actions_are_distinct():
    assert (
        route_ask("What is the latest public news about NVDA?").intent
        is AskIntent.CURRENT_PUBLIC_INFORMATION
    )
    assert (
        route_ask("Execute a trade in my brokerage account").intent
        is AskIntent.UNSUPPORTED
    )


def test_institutional_sector_questions_have_a_dedicated_intent():
    questions = (
        "May I know current investor likely to invest in which sector?",
        "Which sectors are institutional investors buying?",
        "Which sectors does Warren Buffett favor?",
        "What sectors are gaining institutional exposure?",
        "Which sectors are investors likely to invest in next?",
        "Which industries are attracting institutional capital?",
    )
    for question in questions:
        route = route_ask(question)
        assert route.intent is AskIntent.INSTITUTIONAL_SECTOR_ANALYSIS
        assert route.ticker is None


def test_investor_word_alone_does_not_force_company_research():
    route = route_ask("What does an investor need to consider?")
    assert route.intent is AskIntent.GENERAL
    assert route.ticker is None
