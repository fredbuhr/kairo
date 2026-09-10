import {
  createContext,
  useContext,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react'

type ProjectSelectionContextValue = {
  selectedProjectId: string
  setSelectedProjectId: Dispatch<SetStateAction<string>>
}

const ProjectSelectionContext = createContext<ProjectSelectionContextValue | null>(null)

export function ProjectSelectionProvider({ children }: { children: ReactNode }) {
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const value = useMemo(
    () => ({ selectedProjectId, setSelectedProjectId }),
    [selectedProjectId],
  )

  return (
    <ProjectSelectionContext.Provider value={value}>
      {children}
    </ProjectSelectionContext.Provider>
  )
}

export function useProjectSelection(): ProjectSelectionContextValue {
  const value = useContext(ProjectSelectionContext)
  if (!value) {
    throw new Error('Project selection must be used inside ProjectSelectionProvider')
  }
  return value
}
