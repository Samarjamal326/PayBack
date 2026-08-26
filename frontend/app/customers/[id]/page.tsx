import PayBackApp from '@/components/payback-app'
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <PayBackApp view="customer-detail" id={id} /> }
