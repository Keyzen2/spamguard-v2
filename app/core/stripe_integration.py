import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

async def create_customer(user_id: str, email: str) -> str:
    """Create Stripe customer"""
    customer = stripe.Customer.create(
        email=email,
        metadata={'user_id': user_id}
    )
    return customer.id

async def create_subscription(customer_id: str, plan: str) -> Dict:
    """Create subscription"""
    price_id = settings.STRIPE_PRICES[plan]
    
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{'price': price_id}],
        payment_behavior='default_incomplete',
        expand=['latest_invoice.payment_intent']
    )
    
    return {
        'subscription_id': subscription.id,
        'client_secret': subscription.latest_invoice.payment_intent.client_secret
    }

async def handle_webhook(payload: bytes, sig_header: str) -> Dict:
    """Handle Stripe webhook"""
    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
    
    if event.type == 'customer.subscription.created':
        # Activate subscription
        pass
    elif event.type == 'customer.subscription.deleted':
        # Cancel subscription
        pass
    elif event.type == 'invoice.payment_failed':
        # Handle failed payment
        pass
    
    return {'status': 'success'}
