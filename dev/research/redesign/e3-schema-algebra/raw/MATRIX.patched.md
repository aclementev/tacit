
### t1_structural.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| N body: distinct -> DataFrame[S] (override) | ok | ok | ok | ok | ok |
| N dedupe(Orders) keeps exact S | ok | DataFrame[Orders] | tx.DataFrame[t1_structural.Orders] | DataFrame[Orders] | DataFrame[Orders] |
| N dedupe(Products) rejected | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| N dedupe(Payments) has id but no mixin -> rejected | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| P body: name-checked access via type[S] |  | int | int | int | int |
| P body: typo via type[S] rejected | err | ERR(reportAttributeAccessIssue) | ERR(attr-defined) | ERR(unresolved-attribute) | ERR(missing-attribute) |
| P body: typo via df.<name> (ibis __getattr__) | err | ok ! | ok ! | ok ! | ok ! |
| P body: distinct -> DataFrame[S] | ok | ok | ok | ok | ok |
| P body: order_by -> DataFrame[S] | ok | ok | ok | ok | ok |
| P dedupe_p(Orders) | ok | DataFrame[Orders] | tx.DataFrame[t1_structural.Orders] | DataFrame[Orders] | DataFrame[Orders] |
| P dedupe_p(Payments) no mixin needed | ok | DataFrame[Payments] | tx.DataFrame[t1_structural.Payments] | DataFrame[Payments] | DataFrame[Payments] |
| P dedupe_p(Products) rejected | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| P dedupe_p(BadId id:str) rejected | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| P needs_both(Orders) | ok | ok | ok | ok | ok |
| P needs_both(Payments) no event_ts rejected | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| S filter -> DataFrame[S] | ok | ok | ok | ok | ok |
| S mutate -> Table rejected (good) | err | ERR(reportReturnType) | ERR(return-value) | ERR(invalid-return-type) | ERR(bad-return) |
| S retag(mutate) -> DataFrame[S] | ok | ok | ok | ok | ok |
| S type[S].cast (nominal bound) | ok | ok | ok | ok | ok |
| S type[S].cast (Protocol bound has no cast) | err | ERR(reportAttributeAccessIssue) | ERR(attr-defined) | ERR(unresolved-attribute) | ERR(missing-attribute) |
| R conforms(df, HasIdP) Protocol as type[P] arg | ok | DataFrame[HasIdP] | tx.DataFrame[t1_structural.HasIdP] ERR(type-abstract) ! | DataFrame[HasIdP] | DataFrame[HasIdP] |
| T tacit.DataFrame[S: Protocol] violates bound | err | ERR(reportInvalidTypeArguments) | ERR(type-var) | ERR(invalid-type-arguments) | ERR(bad-specialization) |
| T tacit 0.2 distinct -> Table rejected | err | ERR(reportReturnType) | ERR(return-value) | ERR(invalid-return-type) | ERR(bad-return) |

### t2_additive.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| A body needs unchecked wrap | ok | ok | ok | ok | ok |
| A add_score_a(Orders) |  | DataFrame[WithScore[Orders]] | tx.DataFrame[t2_additive.WithScore[t2_additive.Orders]] | DataFrame[WithScore[Orders]] | DataFrame[WithScore[Orders]] |
| A result satisfies ScoredP | ok | ok | ok | ok | ok |
| A result lost Orders.id (want ok) | ok | ERR(reportArgumentType) ! | ERR(type-var) ! | ERR(invalid-argument-type) ! | ERR(bad-specialization) ! |
| A result usable as DataFrame[Orders] (want ok) | ok | ERR(reportAssignmentType) ! | ERR(assignment) ! | ERR(invalid-assignment) ! | ERR(bad-assignment) ! |
| B1 body | ok | ok | ok | ok | ok |
| B1 out=ScoredOrders | ok | DataFrame[ScoredOrders] | tx.DataFrame[t2_additive.ScoredOrders] | DataFrame[ScoredOrders] | DataFrame[ScoredOrders] |
| B1 out=ScoredCustomers for Orders input (want err) | err | ok ! | ok ! | ok ! | ok ! |
| B1 out without score rejected | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| B2 body | ok | ok | ok | ok | ok |
| B2 out=ScoredOrders | ok | DataFrame[ScoredOrders] | tx.DataFrame[t2_additive.ScoredOrders] | DataFrame[ScoredOrders] | DataFrame[ScoredOrders] |
| B2 out=ScoredCustomers for Orders input | err | ERR(reportArgumentType) | ERR(misc) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| B2 out without Scored mixin | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| B2 out has score but not the mixin | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| B2 same fn, other schema | ok | ok | ok | ok | ok |
| B2 result still has id | ok | ok | ok | ok | ok |
| B2 result has score | ok | ok | ok | ok | ok |
| B2 result as DataFrame[Orders] (invariant: want? see notes) | err | ERR(reportAssignmentType) | ERR(assignment) | ERR(invalid-assignment) | ERR(bad-assignment) |
| B2p structural Scored, nominal O <: Orders | ok | DataFrame[OrdersPlusScoreNoMixin] | tx.DataFrame[t2_additive.OrdersPlusScoreNoMixin] | DataFrame[OrdersPlusScoreNoMixin] | DataFrame[OrdersPlusScoreNoMixin] |
| B2m o.extend_to(ScoredOrders) (want DataFrame[ScoredOrders]) | ok | DataFrame[Orders] | tx.DataFrame[t2_additive.Orders] | DataFrame[ScoredOrders] | DataFrame[ScoredOrders] |
| B2m o.extend_to(ScoredCustomers) | err | ERR(reportArgumentType) | ERR(arg-type) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| B2c ScoredOrders.from_mutate(o) | ok | DataFrame[ScoredOrders] | tx.DataFrame[t2_additive.ScoredOrders] | DataFrame[ScoredOrders] | DataFrame[ScoredOrders] |
| B2c ScoredCustomers.from_mutate(o) | err | ERR(reportArgumentType) | ERR(arg-type) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| B2g generic caller cannot name S+Scored | err | ERR(reportArgumentType) | ERR(misc) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| C add_score_c(Orders) |  | Ext[Orders, Scored] | t2_additive.Ext[t2_additive.Orders, t2_additive.Scored] | Ext[Orders, Scored] | Ext[Orders, Scored] |
| C consumer requiring Scored extension | ok | ok | ok | ok | ok |
| C pass through generic step: Ext info lost |  | DataFrame[Orders] | tx.DataFrame[t2_additive.Orders] | DataFrame[Orders] | DataFrame[Orders] |
| C usable as DataFrame[Orders] (subclass) | ok | ok | ok | ok | ok |
| C two extensions: first lost |  | Ext[Orders, Scored] | t2_additive.Ext[t2_additive.Orders, t2_additive.Scored] | Ext[Orders, Scored] | Ext[Orders, Scored] |
| D add_audit(add_score(Orders)) |  | Frame[Orders, Scored, Audited] | t2_additive.Frame[t2_additive.Orders, t2_additive.Scored, t2_additive.Audited] | Frame[Orders, Scored, Audited] | Frame[Orders, Scored, Audited] |
| D consumer: Orders at head | ok | ok | ok | ok | ok |
| D consumer: Scored anywhere (not last) (want ok) | ok | ERR(reportArgumentType) ! | ERR(arg-type) ! | ERR(invalid-argument-type) ! | ERR(bad-argument-type) ! |
| D consumer: Scored last | ok | ok | ok | ok | ok |

### t3_derived.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| a IrisFeatures has petal_length | ok | ok | ok | ok | ok |
| a Sepal (bottom-up pick) has no petal | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| b1 class X(Iris.pick(...)) as base | ok | ok | ERR(misc) ! | ok | ERR(invalid-inheritance) ! |
| b1 class X(pick_opaque(...)) as base | ok | ok | ERR(misc) ! | ok | ERR(invalid-inheritance) ! |
| b1 type[Self] lie: dropped column still visible (want err) | err | ok ! | ok ! | ok ! | ok ! |
| b1 opaque base: petal unknown (want err) | err | ERR(reportArgumentType) | ok ! | ok ! | ok ! |
| b1 opaque base: kept column visible? |  | Unknown ERR(reportAttributeAccessIssue) | Any | Unknown | Unknown |
| b1 alias = Iris.pick(...) usable as type? | ok | ok | ok | ok | ok |
| b1 DataFrame[alias] annotation | ok | ERR(reportInvalidTypeForm) ! | ERR(valid-type) ! | ERR(invalid-type-form) ! | ok |
| b2 class kwarg derive= | ok | ok | ok | ok | ok |
| b2 SepalV has no petal | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| b2 NoSpecies has petal | ok | ok | ok | ok | ok |

### t3b_typeddict.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| U all columns, right types | ok | ok | ok | ok | ok |
| U missing column | err | ERR(reportCallIssue) | ERR(call-arg) | ERR(missing-argument) | ERR(missing-argument) |
| U extra column | err | ERR(reportCallIssue) | ERR(call-arg) | ok ! | ERR(unexpected-keyword) |
| U typo column | err | ERR(reportCallIssue) | ERR(call-arg) | ERR(missing-argument) | ERR(missing-argument) ERR(unexpected-keyword) |
| U wrong expr type (str expr for float) | err | ERR(reportArgumentType) | ERR(arg-type) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| U add_score(score=...) | ok | ok | ok | ok | ok |
| U add_score typo | err | ERR(reportCallIssue) | ERR(call-arg) | ERR(missing-argument) | ERR(missing-argument) ERR(unexpected-keyword) |
| G Unpack[TypeVar bound TypedDict] | ok | ERR(reportGeneralTypeIssues) ERR(reportInvalidTypeForm) ! | ERR(misc) ERR(valid-type) ! | ERR(invalid-type-form) ! | ERR(invalid-annotation) ! |
| X Schema + TypedDict as bases | ok | ERR(reportGeneralTypeIssues) ! | ERR(misc) ! | ERR(invalid-typed-dict-header) ! | ERR(invalid-inheritance) ! |
| 728 closed=True accepted | ok | ok | ok | ERR(unknown-argument) ! | ok |
| 728 extra key on closed TD | err | ERR(reportAssignmentType) | ERR(typeddict-unknown-key) | ERR(invalid-key) | ERR(bad-typed-dict-key) |
| 728 extra_items= accepted | ok | ok | ERR(call-arg) ! | ERR(unknown-argument) ! | ok |
| 728 Unpack[extra_items] accepts any extra Value | ok | ok | ERR(call-arg) ! | ok | ok |
| 728 Unpack[extra_items] rejects non-Value extra | err | ERR(reportArgumentType) | ERR(call-arg) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| 764 TypedDict[{...}] inline | ok | ERR(reportGeneralTypeIssues) ERR(reportInvalidTypeArguments) ERR(reportInvalidTypeForm) ! | ERR(misc) ERR(valid-type) ! | ERR(invalid-type-form) ! | ERR(invalid-annotation) ERR(unknown-name) ! |
| 767 ReadOnly in Protocol accepted | ok | ERR(reportInvalidTypeForm) ! | ERR(valid-type) ! | ERR(invalid-type-form) ! | ERR(invalid-annotation) ! |
| 767 int column satisfies ReadOnly[float] | ok | ERR(reportArgumentType) ! | ok | ERR(invalid-argument-type) ! | ok |
| P int column satisfies @property float | ok | ok | ok | ok | ok |
| P int column vs mutable float attr (invariant) | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |

### t3c_pep_probes.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| 728te closed=True (typing_extensions) | ok | ok | ok | ok | ok |
| 728te extra_items= (typing_extensions) | ok | ok | ERR(call-arg) ! | ok | ok |
| 728te extra key on closed TD | err | ERR(reportAssignmentType) | ERR(typeddict-unknown-key) | ERR(invalid-key) | ERR(bad-typed-dict-key) |
| 728te Unpack[extra_items] any extra Value | ok | ok | ERR(call-arg) ! | ok | ok |
| 728te Unpack[extra_items] non-Value extra | err | ERR(reportArgumentType) | ERR(call-arg) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| 728te Unpack[extra_items] missing required id | err | ERR(reportCallIssue) | ERR(call-arg) | ERR(missing-argument) | ERR(missing-argument) |
| 764te inline TypedDict[{...}] | ok | ERR(reportGeneralTypeIssues) ERR(reportInvalidTypeArguments) ERR(reportInvalidTypeForm) ! | ERR(misc) ERR(valid-type) ! | ERR(invalid-type-form) ! | ERR(invalid-annotation) ERR(unknown-name) ! |

### t3d_codegen_use.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| c pick() result has no petal | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| c rename() result keeps petal | ok | ok | ok | ok | ok |
| c rename() result has label | ok | ok | ok | ok | ok |
| c source has no label | err | ERR(reportArgumentType) | ERR(type-var) | ERR(invalid-argument-type) | ERR(bad-specialization) |
| c extend() result is a subtype (B2 works) | ok | DataFrame[IrisScored] | tx.DataFrame[cg_generated.IrisScored] | DataFrame[IrisScored] | DataFrame[IrisScored] |
| c generated Cols TypedDict | ok | ok | ok | ok | ok |
| c generated Cols TypedDict missing col | err | ERR(reportCallIssue) | ERR(call-arg) | ERR(missing-argument) | ERR(missing-argument) |

### t4_joins.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| J1 join(o, c, OrdersWithCustomer) | ok | DataFrame[OrdersWithCustomer] | tx.DataFrame[Any] | DataFrame[OrdersWithCustomer] | DataFrame[OrdersWithCustomer] |
| J1 result usable by generic steps | ok | ok | ok | ok | ok |
| J1 out not a subclass of right (has the columns though) | err | ERR(reportArgumentType) | ERR(misc) | ERR(invalid-argument-type) | ok ! |
| J1 wrong right input | err | ERR(reportArgumentType) | ERR(misc) | ERR(invalid-argument-type) | ok ! |
| J1 argument order irrelevant | ok | ok | ERR(misc) ! | ok | ok |
| J1c Out.from_join(o, c) | ok | DataFrame[OrdersWithCustomer] | tx.DataFrame[t4_joins.OrdersWithCustomer] | DataFrame[OrdersWithCustomer] | DataFrame[OrdersWithCustomer] |
| J1c out not a subclass of right | err | ERR(reportArgumentType) | ERR(arg-type) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| J1c wrong right input | err | ERR(reportArgumentType) | ERR(arg-type) | ERR(invalid-argument-type) | ERR(bad-argument-type) |
| J1c argument order irrelevant | ok | ok | ok | ok | ok |
| J1 conflicting column types in out schema | err | ERR(reportIncompatibleVariableOverride) | ERR(misc) | ok ! | ERR(inconsistent-inheritance) |
| J2 join2(o, c) |  | Joined[Orders, Customers] | t4_joins.Joined[t4_joins.Orders, t4_joins.Customers] | Joined[Orders, Customers] | Joined[Orders, Customers] |
| J2 right-side columns invisible to generic steps (want ok) | ok | ERR(reportArgumentType) ! | ERR(type-var) ! | ERR(invalid-argument-type) ! | ERR(bad-specialization) ! |

### t3e_plugin_use.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| d pick() assignment | ok | ok | ok | ok | ok |
| d drop() assignment | ok | ok | ok | ok | ok |
| d rename() assignment | ok | ok | ok | ok | ok |
| d extend() assignment | ok | ok | ok | ok | ok |
| d pick() unknown column | err | ok ! | ERR(misc) | ok ! | ok ! |
| d DataFrame[Derived] annotations | ok | ERR(reportInvalidTypeForm) ! | ok | ERR(invalid-type-form) ! | ok |
| d picked column type |  | Unknown ERR(reportAttributeAccessIssue) | float | Unknown ERR(unresolved-attribute) | Unknown ERR(missing-attribute) |
| d pick() result has no petal | err | ok ! | ERR(type-var) | ok ! | ERR(bad-specialization) |
| d drop() result keeps petal | ok | ok | ok | ok | ERR(bad-specialization) ! |
| d rename() result has label | ok | ok | ok | ok | ERR(bad-specialization) ! |
| d extend() result <: Iris (B2) | ok | DataFrame[Iris] ERR(reportArgumentType) ! | tx.DataFrame[t3e_plugin_use.IrisScored] | DataFrame[Iris] ERR(invalid-argument-type) ! | DataFrame[Iris] ERR(bad-argument-type) ERR(bad-specialization) ! |
