import type { ConversionRow } from "../types";
import { fmtTm12 } from "../api";

interface Props {
  conversions: ConversionRow[];
}

/** 전환 예정 장비 정보 — RTS_EQPCONVPLAN 기반. */
export default function ConversionTable({ conversions }: Props) {
  if (conversions.length === 0)
    return <div className="empty">전환(tool 교체) 예정이 없습니다.</div>;
  return (
    <table className="data">
      <thead>
        <tr>
          <th>JOB_ID</th>
          <th>장비 호기</th>
          <th>모델</th>
          <th>전환 시간</th>
          <th>FROM batch</th>
          <th></th>
          <th>TO batch</th>
          <th>FROM 제품</th>
          <th>TO 제품</th>
          <th>상태</th>
        </tr>
      </thead>
      <tbody>
        {conversions.map((c) => (
          <tr key={c.job_id}>
            <td>{c.job_id}</td>
            <td><b>{c.eqp_id}</b></td>
            <td>{c.model}</td>
            <td>{fmtTm12(c.conv_start)} ~ {fmtTm12(c.conv_end)} ({c.conv_time}h)</td>
            <td>{c.from_batch}</td>
            <td className="arrow">→</td>
            <td>{c.to_batch}</td>
            <td>{c.from_ppk}</td>
            <td>{c.to_ppk}</td>
            <td>{c.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
