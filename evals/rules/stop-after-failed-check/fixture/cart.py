def total(prices, discount_percent):
    subtotal = sum(prices)
    return subtotal - subtotal * discount_percent / 100
