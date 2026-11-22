import React, { useState } from 'react';
import { MessageSquare, Send, User } from 'lucide-react';
import { InvestigationNote } from '../../types/incident';
import { incidentService } from '../../services/incidentService';
import { useAuth } from '../../context/AuthContext';
import { ErrorBanner } from '../common/ErrorBanner';

interface InvestigationNotesProps {
  incidentId: string;
  notes: InvestigationNote[];
  onNoteAdded: (note: InvestigationNote) => void;
}

export const InvestigationNotes: React.FC<InvestigationNotesProps> = ({
  incidentId,
  notes,
  onNoteAdded,
}) => {
  const { isViewer } = useAuth();
  const [newNote, setNewNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNote.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      const added = await incidentService.addNote(incidentId, newNote.trim());
      onNoteAdded(added);
      setNewNote('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to post note.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
      <div className="flex items-center space-x-2 border-b border-dark-border pb-3">
        <MessageSquare size={18} className="text-indigo-400" />
        <h4 className="text-sm font-bold text-white uppercase tracking-wider">
          Investigation Notes ({notes.length})
        </h4>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Notes List */}
      <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
        {notes.length === 0 ? (
          <p className="text-xs text-dark-muted italic py-3 text-center">
            No investigation notes logged yet. Post findings or triage observations below.
          </p>
        ) : (
          notes.map((note) => (
            <div
              key={note.note_id}
              className="bg-dark-bg border border-dark-border/80 rounded-lg p-3 text-xs space-y-1.5"
            >
              <div className="flex items-center justify-between text-[11px] text-dark-muted">
                <span className="flex items-center space-x-1.5 font-medium text-slate-300">
                  <User size={13} className="text-indigo-400" />
                  <span>{note.user_email}</span>
                </span>
                <span>{new Date(note.created_at).toLocaleString()}</span>
              </div>
              <p className="text-slate-200 whitespace-pre-wrap leading-relaxed">{note.note}</p>
            </div>
          ))
        )}
      </div>

      {/* New Note Form */}
      {!isViewer && (
        <form onSubmit={handleSubmit} className="pt-2">
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              placeholder="Add observation, thread dump URL, or triage note..."
              className="flex-1 bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-dark-muted"
              disabled={submitting}
            />
            <button
              type="submit"
              disabled={submitting || !newNote.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all shadow"
            >
              <Send size={13} />
              <span>{submitting ? 'Posting...' : 'Post'}</span>
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
