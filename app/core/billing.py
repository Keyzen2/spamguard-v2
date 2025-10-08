PLANS = {
    'free': {
        'name': 'Free',
        'price': 0,
        'requests_per_month': 500,
        'features': [
            'Basic spam detection',
            'API access',
            'Email support'
        ]
    },
    'pro': {
        'name': 'Pro',
        'price': 9,  # EUR
        'requests_per_month': 10_000,
        'features': [
            'Advanced ML detection',
            'Phishing detection',
            'AI-generated detection',
            'Priority support',
            'Webhooks',
            'Analytics dashboard'
        ]
    },
    'business': {
        'name': 'Business',
        'price': 49,
        'requests_per_month': 100_000,
        'features': [
            'Everything in Pro',
            'Custom model training',
            'Dedicated support',
            'SLA 99.9%',
            'White-label option'
        ]
    },
    'enterprise': {
        'name': 'Enterprise',
        'price': None,  # Custom
        'requests_per_month': float('inf'),
        'features': [
            'Everything in Business',
            'On-premise deployment',
            'Custom integration',
            'Dedicated account manager',
            'SLA 99.99%'
        ]
    }
}
