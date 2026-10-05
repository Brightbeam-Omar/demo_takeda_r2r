import { TopBar } from '../components/shell/TopBar'

export function Overview() {
  return (
    <>
      <TopBar title="Overview" />
      <main className="flex-1 overflow-auto p-6" />
    </>
  )
}
