import { useAdaptiveGraphQuality } from './adaptiveQuality'
import {
  MyceliumViewport as BaseMyceliumViewport,
  type MyceliumViewportProps,
} from './MyceliumViewport'

export function AdaptiveMyceliumViewport(props: MyceliumViewportProps) {
  const requested = props.quality || 'auto'
  const resolved = useAdaptiveGraphQuality(requested)
  return <BaseMyceliumViewport {...props} quality={resolved} />
}
