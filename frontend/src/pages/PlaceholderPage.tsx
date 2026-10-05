import { Placeholder } from '../components/common/Placeholder'
import { TopBar } from '../components/shell/TopBar'

export function PlaceholderPage({ title, feature }: { title: string; feature: string }) {
  return (
    <>
      <TopBar title={title} />
      <main className="flex-1 overflow-auto">
        <Placeholder title={title} feature={feature} />
      </main>
    </>
  )
}
