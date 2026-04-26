import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import { apiGet, apiPost } from '@/lib/api';
import { getStoredRole } from '@/lib/auth';

interface MLStats {
  training_samples: number;
  ml_ready: boolean;
  active_model: {
    version: string;
    mape: number;
    rmse: number;
    cv_rmse: number;
    training_samples: number;
    created_at: string;
  } | null;
}

interface TrainResult {
  version: string;
  samples: number;
  train_mape: number;
  train_rmse: number;
  cv_rmse: number;
  cv_folds: number;
}

function StatRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <tr style={{ borderBottom: '1px solid #1e1e38' }}>
      <td style={{ padding: '10px 16px', color: '#888', width: 200 }}>{label}</td>
      <td style={{ padding: '10px 16px', color: '#eee', fontWeight: 'bold' }}>{value}</td>
    </tr>
  );
}

export default function MLPage() {
  const [stats,   setStats]   = useState<MLStats | null>(null);
  const [result,  setResult]  = useState<TrainResult | null>(null);
  const [error,   setError]   = useState('');
  const [training, setTraining] = useState(false);
  const isAdmin = getStoredRole() === 'admin';

  useEffect(() => {
    apiGet<MLStats>('/api/admin/ml/stats').then(setStats).catch(e => setError(e.message));
  }, []);

  async function trainModel() {
    if (!confirm('Start a new model training run? This may take a minute.')) return;
    setTraining(true);
    setError('');
    setResult(null);
    try {
      const r = await apiPost<TrainResult>('/api/admin/ml/train');
      setResult(r);
      // Refresh stats
      const s = await apiGet<MLStats>('/api/admin/ml/stats');
      setStats(s);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setTraining(false);
    }
  }

  const model = stats?.active_model;

  return (
    <Layout>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <h2 style={{ margin: 0, color: '#eee' }}>ML Monitor</h2>
        {isAdmin && (
          <button
            onClick={trainModel}
            disabled={training}
            style={{
              marginLeft: 'auto', padding: '7px 16px',
              background: training ? '#1a3a1a' : '#2a6496',
              color: '#eee', border: 'none', borderRadius: 4,
              cursor: training ? 'not-allowed' : 'pointer', fontSize: 13,
            }}
          >
            {training ? 'Training…' : '⚡ Train new model'}
          </button>
        )}
      </div>

      {error && <div style={{ color: '#FF5555', marginBottom: 12, fontSize: 12 }}>{error}</div>}

      {result && (
        <div style={{
          background: '#0d2a1a', border: '1px solid #2a4a2a', borderRadius: 6,
          padding: '12px 16px', marginBottom: 20, fontSize: 13,
        }}>
          ✓ Training complete: <b>{result.version}</b> &nbsp;&bull;&nbsp;
          {result.samples} samples &nbsp;&bull;&nbsp;
          MAPE {result.train_mape.toFixed(1)}% &nbsp;&bull;&nbsp;
          CV RMSE {result.cv_rmse.toFixed(4)} ({result.cv_folds}-fold)
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Data card */}
        <div style={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 8 }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid #2a2a4a', color: '#888', fontSize: 12 }}>
            TRAINING DATA
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <tbody>
              <StatRow label="Total samples" value={stats?.training_samples ?? '…'} />
              <StatRow label="ML ready" value={
                stats == null ? '…' :
                stats.ml_ready
                  ? <span style={{ color: '#73DF5D' }}>✓ Yes (≥ 100 samples)</span>
                  : <span style={{ color: '#FFB30F' }}>✗ Need {100 - (stats.training_samples ?? 0)} more</span>
              } />
            </tbody>
          </table>
        </div>

        {/* Model card */}
        <div style={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 8 }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid #2a2a4a', color: '#888', fontSize: 12 }}>
            ACTIVE MODEL
          </div>
          {model ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <tbody>
                <StatRow label="Version"   value={model.version} />
                <StatRow label="Samples"   value={model.training_samples} />
                <StatRow label="Train MAPE" value={`${model.mape.toFixed(1)}%`} />
                <StatRow label="Train RMSE" value={model.rmse.toFixed(4)} />
                <StatRow label="CV RMSE"   value={model.cv_rmse?.toFixed(4) ?? '—'} />
                <StatRow label="Trained at" value={new Date(model.created_at).toLocaleString('en-GB')} />
              </tbody>
            </table>
          ) : (
            <div style={{ padding: 16, color: '#555', fontSize: 13 }}>No model trained yet</div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 20, color: '#555', fontSize: 12 }}>
        ML threshold: 100 training samples required before switching from rank-based to XGBoost predictions.
        Current: {stats?.training_samples ?? '?'} samples.
        {stats && stats.training_samples < 100 && (
          <> Need {100 - stats.training_samples} more.</>
        )}
      </div>
    </Layout>
  );
}
