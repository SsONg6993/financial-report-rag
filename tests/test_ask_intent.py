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
