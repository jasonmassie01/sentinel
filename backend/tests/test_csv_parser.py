"""Tests for CSV parsers."""

from app.parsers.csv_parser import (
    parse_fidelity_brokerage,
    parse_schwab_brokerage,
    parse_fidelity_credit_card,
    parse_bank_csv,
)


def test_fidelity_positions():
    csv_content = """Symbol,Description,Quantity,Last Price,Current Value,Cost Basis Total,Gain/Loss Dollar,Gain/Loss Percent
AAPL,APPLE INC,100,185.50,"$18,550.00","$15,000.00","$3,550.00",+23.67%
VTI,VANGUARD TOTAL STOCK MKT,50,220.00,"$11,000.00","$9,500.00","$1,500.00",+15.79%
SPAXX,FIDELITY MONEY MARKET,5000,1.00,"$5,000.00","$5,000.00","$0.00",0.00%
"""
    result = parse_fidelity_brokerage(csv_content)
    assert result.parsed_count == 3
    assert len(result.holdings) == 3
    assert result.holdings[0].asset == "AAPL"
    assert result.holdings[0].quantity == 100
    assert result.holdings[0].current_value == 18550.0
    assert result.holdings[0].cost_basis_total == 15000.0
    assert result.holdings[0].unrealized_gain_loss == 3550.0


def test_fidelity_transactions():
    csv_content = """Run Date,Account,Action,Symbol,Description,Type,Quantity,Price ($),Commission ($),Fees ($),Amount ($)
03/15/2025,Individual,YOU BOUGHT,VTI,VANGUARD TOTAL STOCK MARKET,Cash,10,218.50,0,0,-2185.00
03/10/2025,Individual,DIVIDEND,VTI,VANGUARD TOTAL STOCK MARKET,Cash,0,0,0,0,45.60
03/01/2025,Individual,YOU SOLD,AAPL,APPLE INC,Cash,5,178.25,0,0,891.25
"""
    result = parse_fidelity_brokerage(csv_content)
    assert result.parsed_count == 3
    assert len(result.transactions) == 3

    buy = result.transactions[0]
    assert buy.type == "buy"
    assert buy.asset == "VTI"
    assert buy.quantity == 10
    assert buy.date == "2025-03-15"

    div = result.transactions[1]
    assert div.type == "dividend"
    assert div.tax_relevant is True

    sell = result.transactions[2]
    assert sell.type == "sell"
    assert sell.tax_relevant is True


def test_schwab_positions():
    csv_content = """Positions for account Individual ...XXXX as of 03/15/2025
Symbol,Description,Quantity,Price,Price Change %,Market Value,Day Change %,Day Change $,Cost Basis,Gain/Loss $,Gain/Loss %
SCHD,SCHWAB US DIVIDEND EQUITY,200,$78.50,+0.5%,"$15,700.00",+0.5%,$78.50,"$12,000.00","$3,700.00",+30.83%
Account Total,,,,,"$15,700.00",,,"$12,000.00","$3,700.00",
"""
    result = parse_schwab_brokerage(csv_content)
    assert result.parsed_count == 1
    assert len(result.holdings) == 1
    assert result.holdings[0].asset == "SCHD"
    assert result.holdings[0].current_value == 15700.0


def test_fidelity_credit_card():
    csv_content = """Date,Transaction,Name,Memo,Amount
03/14/2025,DEBIT,AMAZON.COM,AMZN MKTP US,-89.99
03/13/2025,DEBIT,STARBUCKS,STARBUCKS #12345,-5.75
03/12/2025,CREDIT,PAYMENT RECEIVED,AUTOPAY,500.00
"""
    result = parse_fidelity_credit_card(csv_content)
    assert result.parsed_count == 3
    assert result.transactions[0].type == "expense"
    assert result.transactions[0].total_amount == 89.99
    assert result.transactions[0].category == "shopping"  # auto-categorized

    assert result.transactions[1].category == "food"  # Starbucks = dining

    assert result.transactions[2].type == "income"  # payment/credit


def test_bank_csv():
    csv_content = """Date,Description,Debit,Credit
03/14/2025,DIRECT DEPOSIT - EMPLOYER,,3500.00
03/13/2025,XFINITY INTERNET,89.99,
03/12/2025,HEB GROCERY,156.42,
"""
    result = parse_bank_csv(csv_content)
    assert result.parsed_count == 3
    assert result.transactions[0].type == "income"
    assert result.transactions[0].total_amount == 3500.0

    assert result.transactions[1].type == "expense"
    assert result.transactions[1].total_amount == 89.99
    assert result.transactions[1].category == "utilities"  # Xfinity

    assert result.transactions[2].category == "food"  # HEB


def test_bank_csv_single_amount_column():
    csv_content = """Date,Description,Amount
03/14/2025,PAYROLL,2500.00
03/13/2025,NETFLIX,-15.99
"""
    result = parse_bank_csv(csv_content)
    assert result.parsed_count == 2
    assert result.transactions[0].type == "income"
    assert result.transactions[1].type == "expense"
    assert result.transactions[1].total_amount == 15.99


def test_empty_csv():
    result = parse_fidelity_brokerage("")
    assert result.parsed_count == 0
    assert len(result.errors) > 0


def test_bad_dates_handled():
    csv_content = """Run Date,Account,Action,Symbol,Description,Type,Quantity,Price ($),Commission ($),Fees ($),Amount ($)
INVALID,Individual,YOU BOUGHT,VTI,TEST,Cash,10,100,0,0,-1000
"""
    result = parse_fidelity_brokerage(csv_content)
    assert result.parsed_count == 0
    assert len(result.errors) > 0
