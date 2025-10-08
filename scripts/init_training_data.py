"""
Script para cargar dataset inicial - Versión callable
"""
from supabase import create_client
from datetime import datetime
import uuid
import os

def get_spam_comments():
    """Retorna lista de comentarios spam"""
    return [
        "Buy cheap Viagra online! Best prices guaranteed. Click here now: http://pharmacy-cheap.ru",
        "CIALIS 20mg $0.99 per pill! FDA approved. Order now http://meds-online.tk Free shipping worldwide!!!",
        "Generic Viagra, Cialis, Levitra. Lowest prices! http://cheapmeds.cn Fast delivery 24/7",
        "Weight loss pills that work! Lose 30 pounds in 30 days! http://dietpills.ml",
        "Make $5000 per week from home! No experience needed! Click: http://makemoney-fast.ru",
        "Get rich quick! Forex trading secrets revealed! http://forex-secrets.tk Join now!!!",
        "Loan approved! Bad credit OK! $50,000 instant approval http://loans-fast.cn",
        "Bitcoin investment opportunity! Double your money in 30 days! http://crypto-invest.ml",
        "🎰 Best online casino! $5000 welcome bonus! Play now: http://casino-online.tk",
        "Win real money playing slots! Free spins bonus! http://slots-win.cn Click here!!!",
        "Poker online - 200% deposit bonus! Join tournament now! http://poker-pro.ml",
        "Rolex watches $99! Exact copies! http://watches-replica.tk Free shipping worldwide",
        "Designer handbags 90% off! Gucci, Prada, Louis Vuitton http://bags-cheap.cn",
        "Congratulations! You've been selected! Claim your $1000 Amazon gift card: http://prize.ru",
        "YOU ARE A WINNER! Click to claim your prize! http://winner.tk ACT NOW!!!",
        "Your package is waiting! Delivery failed. Update address: http://delivery.cn",
        "Check out these amazing deals! http://deal1.com http://deal2.com http://deal3.com http://deal4.com",
        "<a href='http://spam.com'>Click here</a> for amazing deals! <b>BUY NOW</b>",
        "AMAZING OPPORTUNITY!!! CLICK HERE NOW!!! http://spam.ru LIMITED TIME ONLY!!!",
        "FREE FREE FREE!!! DONT MISS OUT!!! http://free-stuff.tk GET YOURS TODAY!!!",
        "best best best deals deals deals click click click here here here http://spam.ru now now now",
        "Great post! Check out my website for similar content: http://seo-spam.com",
        "Hack any Facebook account! 100% working! http://hack-fb.ru Download now!",
        "Free Netflix accounts! Unlimited access! http://free-netflix.tk Get yours!",
        "Instagram followers - 10000 for $5! http://followers.cn Instant delivery!",
        "Meet hot singles in your area! http://dating.ru No credit card needed!",
        "Live webcams! Beautiful girls online now! http://cams.tk Join free!",
        "Work from home and earn $500 daily! No boss, no schedule! http://workhome.ga",
        "Credit card debt forgiveness! Eliminate your debt fast! http://debt-relief.ru",
        "Sports betting - bet $10 get $100 free! http://betting.ga Register today!!!",
        "Ray-Ban sunglasses $19.99! Authentic quality! http://sunglasses.ml ORDER NOW!!!",
        "iPhone 15 Pro $299! Brand new unlocked! http://phones-cheap.ga Limited stock!!!",
        "Your account has been suspended! Verify now: http://verify-account.ml URGENT!!!",
        "IRS Notice: Tax refund pending. Click to claim: http://irs-refund.ga",
        "<script>alert('spam')</script> Visit http://malware.ru for free software",
        "BEST DEAL EVER!!! BUY NOW!!! http://deals.cn HURRY UP!!!",
        "Nice article. I wrote about this too: http://my-blog.ru http://my-site.tk Visit please!",
        "購買便宜藥品 http://cheap-meds.cn 免費送貨",
        "first comment lol",
        "nice post visit my blog http://spam.com",
        "cool story bro http://mysite.ru",
        "F1RST!!!1! http://first.tk",
        "Essay writing service! A+ guaranteed! http://essays.ml Plagiarism free!",
        "Lottery winner! Claim your prize now! http://lottery-winner.ru YOU WON!!!",
        "Visit my sites: http://site1.ru http://site2.tk http://site3.cn http://site4.ml CLICK ALL!!!",
        "buy buy buy cheap cheap cheap http://cheap.tk fast fast fast delivery delivery delivery",
        "Interesting. See also: http://link1.com, http://link2.com, http://link3.com",
        "Male enhancement pills. Increase size naturally! http://enhancement.ga 100% guaranteed",
        "Заработок в интернете! http://zarabotok.ru Быстро и легко!",
        "Earn $5000 per week working from home! No experience needed!",
        "Limited time offer! BUY NOW ACT FAST!!! http://urgent-deals.ru",
    ]

def get_ham_comments():
    """Retorna lista de comentarios legítimos"""
    return [
        "This is an excellent article! I've been struggling with this problem for weeks, and your explanation finally made it clear. The examples you provided were particularly helpful. Thank you so much for sharing your knowledge!",
        "Great explanation! I implemented your solution and it worked perfectly. One small suggestion: you might want to add a note about the potential memory issues when dealing with large datasets.",
        "Thank you for this comprehensive guide. I have a question about the third step - could you elaborate on why you chose that particular approach? I'm curious about the trade-offs.",
        "I've been following your blog for months and this is one of your best posts yet. The way you break down complex concepts into digestible pieces is really helpful.",
        "As someone who works in this field professionally, I can confirm that your analysis is spot-on. You've captured the nuances that many other articles miss.",
        "This is helpful, but I'm having trouble with the configuration step. When I run the command, I get an error message about missing dependencies. Has anyone else encountered this?",
        "Interesting perspective. Have you considered the impact of recent changes in the API? I'm wondering if your approach would still work with the latest version.",
        "Could you provide more details about the performance implications? I'm working on a similar project and need to optimize for speed.",
        "What would you recommend for beginners who are just starting out? Is there a simplified version of this approach?",
        "Thank you for posting this! Saved me hours of troubleshooting.",
        "Exactly what I was looking for. Bookmarking for future reference.",
        "This helped me solve a critical bug in production. You're a lifesaver!",
        "Clear, concise, and practical. More tutorials should be like this.",
        "I'd like to add that this approach also works well with Docker containers. Here's how I adapted it for my use case...",
        "For anyone interested, I've created a GitHub repository with additional examples based on this tutorial.",
        "An alternative method that might be useful is to use the built-in library function instead. It's less flexible but simpler to implement.",
        "Well explained, thanks!",
        "This is gold. Thank you.",
        "Bookmarked!",
        "Very helpful, appreciated.",
        "Great work!",
        "Thanks for sharing this.",
        "I tried this approach last week and it completely transformed my workflow. The time savings have been incredible.",
        "We implemented this solution at our company and it's been running smoothly for three months now.",
        "I was skeptical at first, but after testing thoroughly, I'm convinced this is the right approach.",
        "Good article overall, but I think there's a small error in step 4. The variable should be initialized before the loop.",
        "While I agree with most of your points, I have a different opinion on the security implications.",
        "Solid content, but the example code could be more readable. Consider adding comments.",
        "I commented earlier about the error I was getting. Just wanted to update that I figured it out - it was a version mismatch issue.",
        "Coming back to this article six months later and it's still relevant. I've shared it with my entire team.",
        "As a teacher, I find this explanation perfect for introducing students to the concept.",
        "From a business perspective, the cost-benefit analysis you provided is very useful.",
        "I'm a visual learner, so the diagrams you included were especially helpful.",
        "The progressive difficulty level is just right for learning this topic.",
        "This will help me make a case to management for implementing this solution.",
        "Any chance you could add a video walkthrough as well?",
        "I appreciate how you addressed common pitfalls that beginners might encounter.",
        "The real-world examples made this much easier to understand.",
        "Following your guide step by step worked flawlessly. Thank you!",
        "This is now my go-to resource for this topic.",
        "I've recommended this article to several colleagues already.",
    ]

def insert_training_data():
    """Función principal para insertar datos"""
    from app.config import get_settings
    from app.features import extract_features
    
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    
    spam_comments = get_spam_comments()
    ham_comments = get_ham_comments()
    
    total_inserted = 0
    errors = []
    
    # Insertar SPAM
    for i, content in enumerate(spam_comments, 1):
        try:
            comment_data = {
                'content': content,
                'author': f'SpamBot{i}',
                'author_email': f'spam{i}@tempmail.com' if i % 3 == 0 else None,
                'author_ip': f'192.168.{i % 255}.{(i * 7) % 255}',
                'post_id': 1,
                'author_url': f'http://spam{i}.ru' if i % 4 == 0 else None,
                'user_agent': 'SpamBot/1.0' if i % 5 == 0 else 'Mozilla/5.0',
                'referer': None
            }
            
            features = extract_features(comment_data)
            
            data = {
                'id': str(uuid.uuid4()),
                'site_id': 'global',
                'comment_content': content,
                'comment_author': comment_data['author'],
                'comment_author_email': comment_data.get('author_email'),
                'comment_author_ip': comment_data['author_ip'],
                'comment_author_url': comment_data.get('author_url'),
                'post_id': 1,
                'features': features,
                'predicted_label': 'spam',
                'actual_label': 'spam',
                'prediction_confidence': 1.0,
                'user_agent': comment_data.get('user_agent'),
                'created_at': datetime.utcnow().isoformat()
            }
            
            supabase.table('comments_analyzed').insert(data).execute()
            total_inserted += 1
            
        except Exception as e:
            errors.append(f"Spam #{i}: {str(e)}")
    
    # Insertar HAM
    for i, content in enumerate(ham_comments, 1):
        try:
            comment_data = {
                'content': content,
                'author': f'User{i}',
                'author_email': f'user{i}@gmail.com',
                'author_ip': f'10.0.{i % 255}.{(i * 3) % 255}',
                'post_id': 1,
                'author_url': f'https://user{i}.com' if i % 5 == 0 else None,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'referer': 'https://google.com'
            }
            
            features = extract_features(comment_data)
            
            data = {
                'id': str(uuid.uuid4()),
                'site_id': 'global',
                'comment_content': content,
                'comment_author': comment_data['author'],
                'comment_author_email': comment_data.get('author_email'),
                'comment_author_ip': comment_data['author_ip'],
                'comment_author_url': comment_data.get('author_url'),
                'post_id': 1,
                'features': features,
                'predicted_label': 'ham',
                'actual_label': 'ham',
                'prediction_confidence': 1.0,
                'user_agent': comment_data.get('user_agent'),
                'created_at': datetime.utcnow().isoformat()
            }
            
            supabase.table('comments_analyzed').insert(data).execute()
            total_inserted += 1
            
        except Exception as e:
            errors.append(f"Ham #{i}: {str(e)}")
    
    # Actualizar stats
    try:
        stats_data = {
            'site_id': 'global',
            'total_analyzed': total_inserted,
            'total_spam_blocked': len(spam_comments),
            'total_ham_approved': len(ham_comments),
            'accuracy': 1.0,
            'api_key': f'sg_global_training_{uuid.uuid4().hex[:16]}',
            'created_at': datetime.utcnow().isoformat()
        }
        supabase.table('site_stats').upsert(stats_data).execute()
    except Exception as e:
        errors.append(f"Stats: {str(e)}")
    
    return {
        'total_inserted': total_inserted,
        'spam_count': len(spam_comments),
        'ham_count': len(ham_comments),
        'errors': errors
    }
