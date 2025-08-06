import CardMessage from './CardMessage';
import QuoteMessage from './QuoteMessage';

const chatData = [
  {
    type: 'message',
    avatar: 'RM',
    message: 'Hi! I need a Duo Subscription quote for 100 users.',
    time: '10:12 AM',
    align: 'left',
    accent: false
  },
  {
    type: 'message',
    avatar: 'CC',
    message: 'Sure! Here is the quote for Duo Subscription (Advantage, 2 years, 100 users):',
    time: '10:13 AM',
    align: 'right',
    accent: true
  },
  {
    type: 'quote',
    avatar: 'CC',
    name: 'XYZ Corp.',
    quoteId: 'Q-2025-001',
    dealId: 'D-998877',
    quoteStatus: 'Pending Approval',
    expiryDate: '08/10/2025',
    priceProtectionExpiry: '08/30/2025',
    priceList: 'Cisco Global 2025',
    time: '10:14 AM',
    items: [
      { description: 'Duo Subscription Advantage', quantity: 100, price: '$120.00' },
      { description: 'Premium Support', quantity: 1, price: '$1,000.00' }
    ],
    total: '$13,000.00',
    align: 'right',
    accent: true
  }
];

export default function MainContainer() {
  return (
    <div className="flex flex-col h-full w-full bg-white rounded-xl shadow-card border border-border overflow-hidden">
      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
        {/* Example messages using CardMessage */}
        {chatData.map((item, idx) =>
          item.type === 'message' ? (
            <CardMessage
              key={idx}
              avatar={item.avatar}
              message={item.message}
              time={item.time}
              align={item.align as 'left' | 'right'}
              accent={item.accent}
            />
          ) : (
            <QuoteMessage
              key={idx}
              avatar={item.avatar || ''}
              name={item.name || ''}
              quoteId={item.quoteId || ''}
              dealId={item.dealId || ''}
              quoteStatus={item.quoteStatus || ''}
              expiryDate={item.expiryDate || ''}
              priceProtectionExpiry={item.priceProtectionExpiry || ''}
              priceList={item.priceList || ''}
              time={item.time || ''}
              items={item.items || []}
              total={item.total || ''}
              align={item.align as 'left' | 'right'}
              accent={item.accent}
            />
          )
        )}
        {/* ...add more mock messages as needed... */}
      </div>
      {/* Bottom menu + input */}
      <div className="border-t border-border bg-grayBg px-6 py-4 flex flex-col gap-2">
        <div className="flex gap-3 mb-3">
          <button className="bg-white border border-accent text-accent rounded-full px-4 py-2 shadow-button hover:bg-secondary hover:text-primary transition-colors font-segoe text-sm font-medium flex items-center gap-2" title="Download Quote">
            {/* Download icon */}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 4v12" /></svg>
            Download Quote
          </button>
          <button className="bg-white border border-accent text-accent rounded-full px-4 py-2 shadow-button hover:bg-secondary hover:text-primary transition-colors font-segoe text-sm font-medium flex items-center gap-2" title="Create Order">
            {/* Order icon (clipboard) */}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" /></svg>
            Create Order
          </button>
          <button className="bg-white border border-accent text-accent rounded-full px-4 py-2 shadow-button hover:bg-secondary hover:text-primary transition-colors font-segoe text-sm font-medium flex items-center gap-2" title="Engage with AM">
            {/* Chat icon */}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M17 8h2a2 2 0 012 2v8a2 2 0 01-2 2H7a2 2 0 01-2-2v-2M15 3H9a2 2 0 00-2 2v12a2 2 0 002 2h6a2 2 0 002-2V5a2 2 0 00-2-2z" /></svg>
            Engage with AM
          </button>
          <button className="bg-white border border-accent text-accent rounded-full px-4 py-2 shadow-button hover:bg-secondary hover:text-primary transition-colors font-segoe text-sm font-medium flex items-center gap-2" title="Draft Email">
            {/* Email icon */}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M16 12H8m8 0a4 4 0 00-8 0m8 0a4 4 0 01-8 0m8 0V8a4 4 0 00-8 0v4" /></svg>
            Draft Email
          </button>
        </div>
        <div className="flex items-center gap-3">
          <input
            className="flex-1 bg-white border border-border rounded-full px-6 h-12 text-neutral focus:outline-none focus:ring-2 focus:ring-accent placeholder:text-light font-segoe"
            placeholder="Type your message..."
          />
          <button className="bg-accent text-white rounded-full px-6 py-2 shadow-button hover:bg-primary transition-colors font-segoe text-base font-medium flex items-center gap-2">
            Send
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" /></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

