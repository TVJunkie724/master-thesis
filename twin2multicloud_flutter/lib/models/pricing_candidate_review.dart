import 'package:equatable/equatable.dart';

class PricingCandidateReportList extends Equatable {
  final String schemaVersion;
  final String provider;
  final String refreshRunId;
  final List<PricingCandidateReport> reports;

  const PricingCandidateReportList({
    required this.schemaVersion,
    required this.provider,
    required this.refreshRunId,
    this.reports = const [],
  });

  factory PricingCandidateReportList.fromJson(Map<String, dynamic> json) {
    return PricingCandidateReportList(
      schemaVersion: json['schema_version']?.toString() ?? '',
      provider: json['provider']?.toString() ?? '',
      refreshRunId: json['refresh_run_id']?.toString() ?? '',
      reports: _list(
        json['reports'],
      ).map((item) => PricingCandidateReport.fromJson(_map(item))).toList(),
    );
  }

  @override
  List<Object?> get props => [schemaVersion, provider, refreshRunId, reports];
}

class PricingCandidateReport extends Equatable {
  final String schemaVersion;
  final String reportId;
  final String provider;
  final String refreshRunId;
  final String intentId;
  final String? expectedModel;
  final String? expectedUnit;
  final PricingCandidateSelection deterministicSelection;
  final PricingAiSuggestion aiSuggestion;
  final List<PricingReviewCandidate> candidates;
  final List<PricingRejectedCandidate> rejectedCandidates;
  final String reviewState;
  final String sourceStatus;
  final String? sourceWarning;
  final DateTime? createdAt;

  const PricingCandidateReport({
    required this.schemaVersion,
    required this.reportId,
    required this.provider,
    required this.refreshRunId,
    required this.intentId,
    this.expectedModel,
    this.expectedUnit,
    required this.deterministicSelection,
    required this.aiSuggestion,
    this.candidates = const [],
    this.rejectedCandidates = const [],
    required this.reviewState,
    required this.sourceStatus,
    this.sourceWarning,
    this.createdAt,
  });

  factory PricingCandidateReport.fromJson(Map<String, dynamic> json) {
    return PricingCandidateReport(
      schemaVersion: json['schema_version']?.toString() ?? '',
      reportId: json['report_id']?.toString() ?? '',
      provider: json['provider']?.toString() ?? '',
      refreshRunId: json['refresh_run_id']?.toString() ?? '',
      intentId: json['intent_id']?.toString() ?? '',
      expectedModel: _string(json['expected_model']),
      expectedUnit: _string(json['expected_unit']),
      deterministicSelection: PricingCandidateSelection.fromJson(
        _map(json['deterministic_selection']),
      ),
      aiSuggestion: PricingAiSuggestion.fromJson(_map(json['ai_suggestion'])),
      candidates: _list(
        json['candidates'],
      ).map((item) => PricingReviewCandidate.fromJson(_map(item))).toList(),
      rejectedCandidates: _list(
        json['rejected_candidates'],
      ).map((item) => PricingRejectedCandidate.fromJson(_map(item))).toList(),
      reviewState: json['review_state']?.toString() ?? 'evidence_unavailable',
      sourceStatus: json['source_status']?.toString() ?? '',
      sourceWarning: _string(json['source_warning']),
      createdAt: _date(json['created_at']),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    reportId,
    provider,
    refreshRunId,
    intentId,
    expectedModel,
    expectedUnit,
    deterministicSelection,
    aiSuggestion,
    candidates,
    rejectedCandidates,
    reviewState,
    sourceStatus,
    sourceWarning,
    createdAt,
  ];
}

class PricingCandidateSelection extends Equatable {
  final String? candidateId;
  final bool selectable;
  final String confidenceLabel;

  const PricingCandidateSelection({
    this.candidateId,
    required this.selectable,
    required this.confidenceLabel,
  });

  factory PricingCandidateSelection.fromJson(Map<String, dynamic> json) {
    return PricingCandidateSelection(
      candidateId: _string(json['candidate_id']),
      selectable: json['selectable'] == true,
      confidenceLabel: json['confidence_label']?.toString() ?? '',
    );
  }

  @override
  List<Object?> get props => [candidateId, selectable, confidenceLabel];
}

class PricingAiSuggestion extends Equatable {
  final bool enabled;
  final String? candidateId;
  final String rationale;

  const PricingAiSuggestion({
    required this.enabled,
    this.candidateId,
    required this.rationale,
  });

  factory PricingAiSuggestion.fromJson(Map<String, dynamic> json) {
    return PricingAiSuggestion(
      enabled: json['enabled'] == true,
      candidateId: _string(json['candidate_id']),
      rationale: json['rationale']?.toString() ?? '',
    );
  }

  @override
  List<Object?> get props => [enabled, candidateId, rationale];
}

class PricingReviewCandidate extends Equatable {
  final String candidateId;
  final String sourceType;
  final String fieldPath;
  final String? service;
  final String? field;
  final Object? value;
  final String? currency;
  final String? unit;
  final String sourceLabel;
  final String evidenceStatus;
  final Map<String, dynamic>? selectedRow;

  const PricingReviewCandidate({
    required this.candidateId,
    required this.sourceType,
    required this.fieldPath,
    this.service,
    this.field,
    this.value,
    this.currency,
    this.unit,
    required this.sourceLabel,
    required this.evidenceStatus,
    this.selectedRow,
  });

  factory PricingReviewCandidate.fromJson(Map<String, dynamic> json) {
    return PricingReviewCandidate(
      candidateId: json['candidate_id']?.toString() ?? '',
      sourceType: json['source_type']?.toString() ?? '',
      fieldPath: json['field_path']?.toString() ?? '',
      service: _string(json['service']),
      field: _string(json['field']),
      value: json['value'],
      currency: _string(json['currency']),
      unit: _string(json['unit']),
      sourceLabel: json['source_label']?.toString() ?? '',
      evidenceStatus: json['evidence_status']?.toString() ?? '',
      selectedRow: json['selected_row'] is Map
          ? Map<String, dynamic>.from(json['selected_row'] as Map)
          : null,
    );
  }

  @override
  List<Object?> get props => [
    candidateId,
    sourceType,
    fieldPath,
    service,
    field,
    value,
    currency,
    unit,
    sourceLabel,
    evidenceStatus,
    selectedRow,
  ];
}

class PricingRejectedCandidate extends Equatable {
  final String candidateId;
  final List<String> reasons;
  final Map<String, dynamic>? selectedRow;

  const PricingRejectedCandidate({
    required this.candidateId,
    this.reasons = const [],
    this.selectedRow,
  });

  factory PricingRejectedCandidate.fromJson(Map<String, dynamic> json) {
    return PricingRejectedCandidate(
      candidateId: json['candidate_id']?.toString() ?? '',
      reasons: _strings(json['reasons']),
      selectedRow: json['selected_row'] is Map
          ? Map<String, dynamic>.from(json['selected_row'] as Map)
          : null,
    );
  }

  @override
  List<Object?> get props => [candidateId, reasons, selectedRow];
}

class PricingTrace extends Equatable {
  final String schemaVersion;
  final String reportId;
  final String provider;
  final Map<String, dynamic> intent;
  final Map<String, dynamic> queryScope;
  final Map<String, dynamic>? selectedCandidate;
  final List<Map<String, dynamic>> closeCandidates;
  final List<Map<String, dynamic>> rejectedCandidates;
  final List<Map<String, dynamic>> hardChecks;
  final Map<String, dynamic> normalization;
  final String? formulaRef;
  final PricingTraceSanitization sanitization;

  const PricingTrace({
    required this.schemaVersion,
    required this.reportId,
    required this.provider,
    this.intent = const {},
    this.queryScope = const {},
    this.selectedCandidate,
    this.closeCandidates = const [],
    this.rejectedCandidates = const [],
    this.hardChecks = const [],
    this.normalization = const {},
    this.formulaRef,
    required this.sanitization,
  });

  factory PricingTrace.fromJson(Map<String, dynamic> json) {
    return PricingTrace(
      schemaVersion: json['schema_version']?.toString() ?? '',
      reportId: json['report_id']?.toString() ?? '',
      provider: json['provider']?.toString() ?? '',
      intent: _map(json['intent']),
      queryScope: _map(json['query_scope']),
      selectedCandidate: json['selected_candidate'] is Map
          ? _map(json['selected_candidate'])
          : null,
      closeCandidates: _maps(json['close_candidates']),
      rejectedCandidates: _maps(json['rejected_candidates']),
      hardChecks: _maps(json['hard_checks']),
      normalization: _map(json['normalization']),
      formulaRef: _string(json['formula_ref']),
      sanitization: PricingTraceSanitization.fromJson(
        _map(json['sanitization']),
      ),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    reportId,
    provider,
    intent,
    queryScope,
    selectedCandidate,
    closeCandidates,
    rejectedCandidates,
    hardChecks,
    normalization,
    formulaRef,
    sanitization,
  ];
}

class PricingTraceSanitization extends Equatable {
  final bool bounded;
  final bool secretFree;
  final int omittedRawRows;

  const PricingTraceSanitization({
    required this.bounded,
    required this.secretFree,
    required this.omittedRawRows,
  });

  factory PricingTraceSanitization.fromJson(Map<String, dynamic> json) {
    return PricingTraceSanitization(
      bounded: json['bounded'] == true,
      secretFree: json['secret_free'] == true,
      omittedRawRows: _integer(json['omitted_raw_rows']),
    );
  }

  @override
  List<Object?> get props => [bounded, secretFree, omittedRawRows];
}

class PricingReviewDecision extends Equatable {
  final String schemaVersion;
  final String decisionId;
  final String reportId;
  final String provider;
  final String intentId;
  final String decision;
  final String? selectedCandidateId;
  final String? rationale;
  final DateTime? createdAt;

  const PricingReviewDecision({
    required this.schemaVersion,
    required this.decisionId,
    required this.reportId,
    required this.provider,
    required this.intentId,
    required this.decision,
    this.selectedCandidateId,
    this.rationale,
    this.createdAt,
  });

  factory PricingReviewDecision.fromJson(Map<String, dynamic> json) {
    return PricingReviewDecision(
      schemaVersion: json['schema_version']?.toString() ?? '',
      decisionId: json['decision_id']?.toString() ?? '',
      reportId: json['report_id']?.toString() ?? '',
      provider: json['provider']?.toString() ?? '',
      intentId: json['intent_id']?.toString() ?? '',
      decision: json['decision']?.toString() ?? '',
      selectedCandidateId: _string(json['selected_candidate_id']),
      rationale: _string(json['rationale']),
      createdAt: _date(json['created_at']),
    );
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    decisionId,
    reportId,
    provider,
    intentId,
    decision,
    selectedCandidateId,
    rationale,
    createdAt,
  ];
}

Map<String, dynamic> _map(dynamic value) {
  return value is Map ? Map<String, dynamic>.from(value) : const {};
}

List<dynamic> _list(dynamic value) => value is List ? value : const [];

List<Map<String, dynamic>> _maps(dynamic value) {
  return _list(value).whereType<Map>().map(_map).toList();
}

List<String> _strings(dynamic value) {
  return _list(value).map((item) => item.toString()).toList();
}

String? _string(dynamic value) {
  if (value == null) return null;
  final text = value.toString();
  return text.isEmpty ? null : text;
}

DateTime? _date(dynamic value) {
  return value == null ? null : DateTime.tryParse(value.toString());
}

int _integer(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}
