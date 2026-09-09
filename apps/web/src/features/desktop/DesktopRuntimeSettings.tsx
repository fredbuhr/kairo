import { useMutation, useQuery } from '@tanstack/react-query'

import {
  fetchDesktopCapabilities,
  sendDesktopNotification,
  writeDesktopClipboard,
} from '../../lib/desktopBridge'
import { AuthIdentitySettings } from '../auth/AuthIdentitySettings'

function availability(value: boolean) {
  return value ? 'Disponible' : 'Non activé'
}

export function DesktopRuntimeSettings() {
  const capabilitiesQuery = useQuery({
    queryKey: ['desktop-capabilities'],
    queryFn: fetchDesktopCapabilities,
    staleTime: Infinity,
    retry: false,
  })
  const capabilities = capabilitiesQuery.data
  const notify = useMutation({
    mutationFn: () => sendDesktopNotification(
      'KAIRO Desktop',
      'Les notifications locales sont reliées au bridge KAIRO.',
    ),
  })
  const copyDiagnostic = useMutation({
    mutationFn: async () => {
      if (!capabilities) return
      const diagnostic = [
        `KAIRO ${capabilities.runtime === 'tauri' ? 'Desktop' : 'Web'}`,
        capabilities.app_version ? `version ${capabilities.app_version}` : null,
        capabilities.platform ? `${capabilities.platform}/${capabilities.arch || 'unknown'}` : null,
        `clipboard=${capabilities.clipboard_write ? 'yes' : 'no'}`,
        `notifications=${capabilities.notifications ? 'yes' : 'no'}`,
        `summon=${capabilities.summon_shortcut_label || 'no'}`,
        `microphone=${capabilities.microphone ? 'yes' : 'no'}`,
        `screenshots=${capabilities.screenshots ? 'yes' : 'no'}`,
      ].filter(Boolean).join(' · ')
      await writeDesktopClipboard(diagnostic)
    },
  })

  let runtimePanel
  if (capabilitiesQuery.isLoading) {
    runtimePanel = <section className="desktop-runtime-settings"><span>Détection de l’environnement local…</span></section>
  } else if (capabilitiesQuery.isError || !capabilities) {
    runtimePanel = (
      <section className="desktop-runtime-settings desktop-runtime-error">
        <strong>Bridge Desktop indisponible</strong>
        <span>Le Cockpit reste utilisable comme application Web.</span>
      </section>
    )
  } else {
    const desktop = capabilities.runtime === 'tauri'
    const actionError = notify.error || copyDiagnostic.error
    runtimePanel = (
      <section className="desktop-runtime-settings">
        <header>
          <div>
            <span className="kairo-kicker">ENVIRONNEMENT</span>
            <strong>{desktop ? 'KAIRO Desktop connecté' : 'KAIRO Web'}</strong>
          </div>
          <b>{desktop ? 'LOCAL BRIDGE' : 'NAVIGATEUR'}</b>
        </header>
        <p>
          {desktop
            ? `Tauri ${capabilities.app_version || ''} · ${capabilities.platform || 'plateforme'} ${capabilities.arch || ''}`
            : 'Les capacités locales sensibles restent désactivées dans le navigateur.'}
        </p>
        <dl>
          <div><dt>Import de fichiers</dt><dd>{capabilities.file_import === 'web_file_input' ? 'Sélection explicite' : 'Non activé'}</dd></div>
          <div><dt>Presse-papiers</dt><dd>{availability(capabilities.clipboard_read && capabilities.clipboard_write)}</dd></div>
          <div><dt>Notifications</dt><dd>{availability(capabilities.notifications)}</dd></div>
          <div><dt>Capture écran</dt><dd>{availability(capabilities.screenshots)}</dd></div>
          <div><dt>Microphone</dt><dd>{availability(capabilities.microphone)}</dd></div>
          <div><dt>Raccourci d’invocation</dt><dd>{capabilities.summon_shortcut ? capabilities.summon_shortcut_label || 'Disponible' : 'Non activé'}</dd></div>
        </dl>
        {desktop && (
          <div className="desktop-runtime-actions">
            <button type="button" disabled={!capabilities.notifications || notify.isPending} onClick={() => notify.mutate()}>
              {notify.isPending ? 'Envoi…' : 'Tester la notification'}
            </button>
            <button type="button" disabled={!capabilities.clipboard_write || copyDiagnostic.isPending} onClick={() => copyDiagnostic.mutate()}>
              {copyDiagnostic.isPending ? 'Copie…' : 'Copier le diagnostic'}
            </button>
          </div>
        )}
        {actionError && (
          <small className="workspace-error">
            {actionError instanceof Error ? actionError.message : 'La capacité locale a été refusée.'}
          </small>
        )}
      </section>
    )
  }

  return (
    <>
      <AuthIdentitySettings />
      {runtimePanel}
    </>
  )
}
