import { NextRequest, NextResponse } from 'next/server'
import { stripe } from '@/lib/stripe'
import { createServiceClient } from '@/lib/supabase-server'
import Stripe from 'stripe'

export async function POST(request: NextRequest) {
  const body = await request.text()
  const sig = request.headers.get('stripe-signature')!

  let event: Stripe.Event
  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!)
  } catch {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 })
  }

  const supabase = await createServiceClient()

  switch (event.type) {
    // 月訂閱付款成功
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.CheckoutSession
      const userId = session.metadata?.user_id
      const plan = session.metadata?.plan
      if (!userId || !plan) break

      if (plan === 'day_pass') {
        const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
        await supabase.from('subscriptions').upsert({
          user_id: userId,
          plan_type: 'day_pass',
          status: 'active',
          expires_at: expiresAt,
          stripe_customer_id: session.customer as string,
        })
      }
      break
    }

    // 月訂閱付款確認（subscription 啟動）
    case 'customer.subscription.created':
    case 'customer.subscription.updated': {
      const sub = event.data.object as Stripe.Subscription
      const userId = sub.metadata?.user_id

      // 從 session 取 user_id（subscription 可能沒有直接 metadata）
      const customerId = sub.customer as string
      const { data: existing } = await supabase
        .from('subscriptions')
        .select('user_id')
        .eq('stripe_customer_id', customerId)
        .limit(1)
        .single()

      const uid = userId || existing?.user_id
      if (!uid) break

      const isActive = sub.status === 'active' || sub.status === 'trialing'
      const expiresAt = new Date((sub.current_period_end ?? 0) * 1000).toISOString()

      await supabase.from('subscriptions').upsert({
        user_id: uid,
        plan_type: 'monthly',
        status: isActive ? 'active' : 'cancelled',
        expires_at: expiresAt,
        stripe_customer_id: customerId,
        stripe_subscription_id: sub.id,
      })
      break
    }

    // 訂閱取消
    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription
      await supabase
        .from('subscriptions')
        .update({ status: 'cancelled' })
        .eq('stripe_subscription_id', sub.id)
      break
    }
  }

  return NextResponse.json({ received: true })
}
