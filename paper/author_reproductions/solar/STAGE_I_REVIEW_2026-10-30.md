# SOLAR Stage I：待人工审核的 SARA 开发规则包

本轮按原作者Stage I处理完整SARA statute。4次远程模型请求，L05累计6/100；不是中国法律规则包或产品完成验收。

原源码[knowledge_acquisition.py](../../upstream_sources/solar/solar/knowledge_acquisition.py) / [固定版本](https://github.com/albsadowski/solar/blob/067f8f78b128dc7647c8a54b2560a612fae91a87/solar/knowledge_acquisition.py)。原human_review_node写明 `Approve (type 'approve')`，decide_after_human_review仅在输入approve后进入code_generation。当前没有代填该输入，未生成/执行新解释器，也未训练评估。

## 审核结论待填写

自动检查：24类、71属性、21规则；最终作者validate_tbox返回空问题列表。首次校验发现date不是支持的数据类型，原integration修订后再次通过。它只检查结构/引用/逻辑表达式，不证明条款语义、数值、覆盖率或法律准确。

本次需决定：是否把下列实际生成TBox接受为SARA开发复现实验规则包，继续原code_generation与训练样例反馈；这不构成中国法律有效性或专家金标认可。可以提供具体修订意见，或保留SOLAR待审核而继续其他API方法。

[实际TBox JSON](../results/2026-10-29-per-paper/methods/solar/runs/c0d9a6be0adebf24__native_acquisition/solar.tbox.json) · [完整输出/阶段状态](../results/2026-10-29-per-paper/methods/solar/runs/c0d9a6be0adebf24__native_acquisition/solar.output.json) · [原始请求回复](../results/2026-10-29-per-paper/methods/solar/runs/c0d9a6be0adebf24__native_acquisition/solar.model_responses.json)

## 原人工审核节点实际输出

```text

==================================================
REVIEW
==================================================

Valid TBox.

Classes:
  - Person: An individual human being, including taxpayers, spouses, dependents, employees, and employers.
  - Employer: A person who employs individuals and pays wages, subject to excise tax under §3301.
  - Employee: An individual who performs services for an employer and receives remuneration.
  - Taxpayer: An individual subject to income tax under §1, including married individuals, surviving spouses, heads of households, and unmarried individuals.
  - Spouse: A married individual's partner, relevant for filing status and exemptions.
  - Dependent: An individual who qualifies as a dependent under §152, including qualifying children and qualifying relatives.
  - QualifyingChild: A child who meets the relationship, abode, age, and joint return tests under §152(c).
  - QualifyingRelative: An individual who meets the relationship, income, and dependency tests under §152(d).
  - SurvivingSpouse: A taxpayer whose spouse died in one of the two preceding years and who maintains a household for a dependent child, as defined in §2(a).
  - HeadOfHousehold: An individual who is not married or a surviving spouse and maintains a household for a qualifying child or dependent, as defined in §2(b).
  - Wages: All remuneration for employment, including cash and non-cash benefits, subject to exceptions under §3306(b).
  - Employment: Any service performed by an employee for an employer, subject to exceptions under §3306(c).
  - TaxableIncome: Gross income minus deductions (other than standard deduction) or adjusted gross income minus standard deduction and personal exemptions, as defined in §63.
  - GrossIncome: Total income from all sources before deductions.
  - AdjustedGrossIncome: Gross income minus certain deductions (above-the-line), used in §63(b) and §68.
  - Deduction: An amount allowed as a deduction from gross income or adjusted gross income, including standard and itemized deductions.
  - StandardDeduction: The sum of the basic standard deduction and additional standard deduction under §63(c).
  - ItemizedDeductions: Deductions allowable under this chapter other than those in arriving at adjusted gross income and personal exemptions, as defined in §63(d).
  - PersonalExemption: An exemption amount allowed as a deduction for the taxpayer, spouse, and dependents under §151.
  - TaxableYear: The calendar year or fiscal year for which tax is determined.
  - CalendarYear: A period of 12 months from January 1 to December 31.
  - FilingStatus: The category under which a taxpayer files a return: married filing jointly, surviving spouse, head of household, unmarried individual, or married filing separately.
  - TaxRateBracket: A range of taxable income with a corresponding tax rate and base amount, as specified in §1.
  - Household: A home maintained by a taxpayer, used in determining head of household and surviving spouse status.

Properties:
  - isEmployer (unary): Indicates whether a person is an employer as defined in §3306(a).
    arguments: ['Person']
  - isNotEmployer (unary): Indicates whether a person is not an employer.
    arguments: ['Person']
  - isEmployee (unary): Indicates whether a person is an employee.
    arguments: ['Person']
  - isNotEmployee (unary): Indicates whether a person is not an employee.
    arguments: ['Person']
  - isTaxpayer (unary): Indicates whether a person is a taxpayer.
    arguments: ['Person']
  - isNotTaxpayer (unary): Indicates whether a person is not a taxpayer.
    arguments: ['Person']
  - isDependent (unary): Indicates whether a person is a dependent under §152.
    arguments: ['Person']
  - isNotDependent (unary): Indicates whether a person is not a dependent.
    arguments: ['Person']
  - isQualifyingChild (unary): Indicates whether a person is a qualifying child under §152(c).
    arguments: ['Person']
  - isNotQualifyingChild (unary): Indicates whether a person is not a qualifying child.
    arguments: ['Person']
  - isQualifyingRelative (unary): Indicates whether a person is a qualifying relative under §152(d).
    arguments: ['Person']
  - isNotQualifyingRelative (unary): Indicates whether a person is not a qualifying relative.
    arguments: ['Person']
  - isSurvivingSpouse (unary): Indicates whether a person is a surviving spouse under §2(a).
    arguments: ['Person']
  - isNotSurvivingSpouse (unary): Indicates whether a person is not a surviving spouse.
    arguments: ['Person']
  - isHeadOfHousehold (unary): Indicates whether a person is a head of household under §2(b).
    arguments: ['Person']
  - isNotHeadOfHousehold (unary): Indicates whether a person is not a head of household.
    arguments: ['Person']
  - isMarried (unary): Indicates whether a person is married as determined under §7703.
    arguments: ['Person']
  - isNotMarried (unary): Indicates whether a person is not married.
    arguments: ['Person']
  - isBlind (unary): Indicates whether a person is blind at the close of the taxable year.
    arguments: ['Person']
  - isNotBlind (unary): Indicates whether a person is not blind.
    arguments: ['Person']
  - isAged (unary): Indicates whether a person has attained age 65 before the close of the taxable year.
    arguments: ['Person']
  - isNotAged (unary): Indicates whether a person has not attained age 65.
    arguments: ['Person']
  - isNonresidentAlien (unary): Indicates whether a person is a nonresident alien.
    arguments: ['Person']
  - isNotNonresidentAlien (unary): Indicates whether a person is not a nonresident alien.
    arguments: ['Person']
  - isLegallySeparated (unary): Indicates whether a person is legally separated under a decree of divorce or separate maintenance.
    arguments: ['Person']
  - isNotLegallySeparated (unary): Indicates whether a person is not legally separated.
    arguments: ['Person']
  - isCommittedToPenalInstitution (unary): Indicates whether a person is committed to a penal institution.
    arguments: ['Person']
  - isNotCommittedToPenalInstitution (unary): Indicates whether a person is not committed to a penal institution.
    arguments: ['Person']
  - hasSpouse (object): Relates a person to their spouse.
    arguments: ['Person', 'Person']
  - hasEmployer (object): Relates an employee to their employer.
    arguments: ['Person', 'Person']
  - hasEmployee (object): Relates an employer to an employee.
    arguments: ['Person', 'Person']
  - hasDependent (object): Relates a taxpayer to a dependent.
    arguments: ['Person', 'Person']
  - isDependentOf (object): Relates a dependent to the taxpayer claiming them.
    arguments: ['Person', 'Person']
  - hasChild (object): Relates a person to their child.
    arguments: ['Person', 'Person']
  - hasParent (object): Relates a person to their parent.
    arguments: ['Person', 'Person']
  - maintainsHousehold (object): Relates a person to a household they maintain.
    arguments: ['Person', 'Household']
  - hasPrincipalPlaceOfAbode (object): Relates a person to their principal place of abode.
    arguments: ['Person', 'Household']
  - hasFilingStatus (object): Relates a taxpayer to their filing status.
    arguments: ['Person', 'FilingStatus']
  - hasTaxableYear (object): Relates a taxpayer to their taxable year.
    arguments: ['Person', 'TaxableYear']
  - hasWages (object): Relates an employee to wages received.
    arguments: ['Person', 'Wages']
  - hasEmployment (object): Relates an employee to an employment relationship.
    arguments: ['Person', 'Employment']
  - hasGrossIncome (object): Relates a taxpayer to their gross income.
    arguments: ['Person', 'GrossIncome']
  - hasAdjustedGrossIncome (object): Relates a taxpayer to their adjusted gross income.
    arguments: ['Person', 'AdjustedGrossIncome']
  - hasTaxableIncome (object): Relates a taxpayer to their taxable income.
    arguments: ['Person', 'TaxableIncome']
  - hasDeduction (object): Relates a taxpayer to a deduction.
    arguments: ['Person', 'Deduction']
  - hasStandardDeduction (object): Relates a taxpayer to their standard deduction.
    arguments: ['Person', 'StandardDeduction']
  - hasItemizedDeductions (object): Relates a taxpayer to their itemized deductions.
    arguments: ['Person', 'ItemizedDeductions']
  - hasPersonalExemption (object): Relates a taxpayer to a personal exemption.
    arguments: ['Person', 'PersonalExemption']
  - hasTaxRateBracket (object): Relates a filing status to applicable tax rate brackets.
    arguments: ['FilingStatus', 'TaxRateBracket']
  - wageAmount (datatype): The monetary amount of wages.
    arguments: ['Wages', 'decimal']
  - grossIncomeAmount (datatype): The monetary amount of gross income.
    arguments: ['GrossIncome', 'decimal']
  - adjustedGrossIncomeAmount (datatype): The monetary amount of adjusted gross income.
    arguments: ['AdjustedGrossIncome', 'decimal']
  - taxableIncomeAmount (datatype): The monetary amount of taxable income.
    arguments: ['TaxableIncome', 'decimal']
  - deductionAmount (datatype): The monetary amount of a deduction.
    arguments: ['Deduction', 'decimal']
  - standardDeductionAmount (datatype): The monetary amount of the standard deduction.
    arguments: ['StandardDeduction', 'decimal']
  - itemizedDeductionAmount (datatype): The monetary amount of itemized deductions.
    arguments: ['ItemizedDeductions', 'decimal']
  - exemptionAmount (datatype): The monetary amount of a personal exemption.
    arguments: ['PersonalExemption', 'decimal']
  - bracketThreshold (datatype): The upper income threshold for a tax rate bracket.
    arguments: ['TaxRateBracket', 'decimal']
  - bracketRate (datatype): The tax rate for a bracket, expressed as a decimal.
    arguments: ['TaxRateBracket', 'decimal']
  - bracketBaseAmount (datatype): The base tax amount for a bracket.
    arguments: ['TaxRateBracket', 'decimal']
  - taxYear (datatype): The year of the taxable year.
    arguments: ['TaxableYear', 'integer']
  - dateOfBirth (datatype): The date of birth of a person, represented as an ISO 8601 string.
    arguments: ['Person', 'string']
  - dateOfDeath (datatype): The date of death of a person, represented as an ISO 8601 string.
    arguments: ['Person', 'string']
  - dateOfMarriage (datatype): The date a person got married, represented as an ISO 8601 string.
    arguments: ['Person', 'string']
  - numberOfEmployees (datatype): The number of employees employed by an employer.
    arguments: ['Person', 'integer']
  - numberOfDaysEmployed (datatype): The number of days on which an employer employed at least one individual.
    arguments: ['Person', 'integer']
  - householdMaintenanceCost (datatype): The cost of maintaining a household.
    arguments: ['Household', 'decimal']
  - isJointReturn (datatype): Indicates whether a taxpayer files a joint return.
    arguments: ['Person', 'boolean']
  - isNotJointReturn (datatype): Indicates whether a taxpayer does not file a joint return.
    arguments: ['Person', 'boolean']
  - itemizesDeductions (datatype): Indicates whether a taxpayer elects to itemize deductions.
    arguments: ['Person', 'boolean']
  - doesNotItemizeDeductions (datatype): Indicates whether a taxpayer does not elect to itemize deductions.
    arguments: ['Person', 'boolean']

Rules:
  - An employer that has individuals in employment is subject to an excise tax with respect to having individuals in employ.
    FOL: isEmployer(X) & hasEmployee(X, Y)
    Implies: SubjectToExciseTax(Employer)
  - A married individual who files a joint return qualifies for joint filing status.
    FOL: isMarried(X) & isJointReturn(X, true)
    Implies: QualifiesForJointFilingStatus(Taxpayer)
  - A surviving spouse qualifies for joint filing status.
    FOL: isSurvivingSpouse(X)
    Implies: QualifiesForJointFilingStatus(Taxpayer)
  - A head of household qualifies for head of household filing status.
    FOL: isHeadOfHousehold(X)
    Implies: QualifiesForHeadOfHouseholdStatus(Taxpayer)
  - An individual who is not a married individual, not a surviving spouse, and not a head of household qualifies for single filing status.
    FOL: isTaxpayer(X) & isNotMarried(X) & isNotSurvivingSpouse(X) & isNotHeadOfHousehold(X)
    Implies: QualifiesForSingleFilingStatus(Taxpayer)
  - A married individual who does not file a joint return qualifies for married filing separately status.
    FOL: isMarried(X) & isNotJointReturn(X, true)
    Implies: QualifiesForMarriedFilingSeparatelyStatus(Taxpayer)
  - A taxpayer who does not elect to itemize deductions uses the standard deduction.
    FOL: isTaxpayer(X) & doesNotItemizeDeductions(X, true)
    Implies: UsesStandardDeduction(Taxpayer)
  - A taxpayer who is aged is entitled to an additional standard deduction.
    FOL: isTaxpayer(X) & isAged(X)
    Implies: EntitledToAdditionalStandardDeduction(Taxpayer)
  - A taxpayer who is blind is entitled to an additional standard deduction.
    FOL: isTaxpayer(X) & isBlind(X)
    Implies: EntitledToAdditionalStandardDeduction(Taxpayer)
  - A taxpayer whose spouse is aged is entitled to an additional standard deduction for the spouse.
    FOL: isTaxpayer(X) & hasSpouse(X, Y) & isAged(Y)
    Implies: EntitledToAdditionalStandardDeductionForSpouse(Taxpayer)
  - A taxpayer whose spouse is blind is entitled to an additional standard deduction for the spouse.
    FOL: isTaxpayer(X) & hasSpouse(X, Y) & isBlind(Y)
    Implies: EntitledToAdditionalStandardDeductionForSpouse(Taxpayer)
  - A taxpayer whose spouse died in the preceding two years, who maintains a household for a dependent child, and is entitled to a deduction for the child is a surviving spouse.
    FOL: isTaxpayer(X) & hasSpouse(X, Y) & dateOfDeath(Y, D) & maintainsHousehold(X, H) & hasChild(X, Z) & isDependent(Z) & hasDeduction(X, DED)
    Implies: IsSurvivingSpouse(Taxpayer)
  - An individual who is not married, not a surviving spouse, and maintains a household for a qualifying child is a head of household.
    FOL: isTaxpayer(X) & isNotMarried(X) & isNotSurvivingSpouse(X) & maintainsHousehold(X, H) & hasChild(X, Y) & isQualifyingChild(Y)
    Implies: IsHeadOfHousehold(Taxpayer)
  - An individual who is not married, not a surviving spouse, and maintains a household for a dependent is a head of household.
    FOL: isTaxpayer(X) & isNotMarried(X) & isNotSurvivingSpouse(X) & maintainsHousehold(X, H) & hasDependent(X, Y) & isDependent(Y)
    Implies: IsHeadOfHousehold(Taxpayer)
  - An individual who is not married, not a surviving spouse, and maintains a household for a parent for whom the taxpayer is entitled to a deduction is a head of household.
    FOL: isTaxpayer(X) & isNotMarried(X) & isNotSurvivingSpouse(X) & maintainsHousehold(X, H) & hasParent(X, Y) & hasDeduction(X, DED)
    Implies: IsHeadOfHousehold(Taxpayer)
  - An individual who is legally separated under a decree of divorce or separate maintenance is not considered married.
    FOL: isTaxpayer(X) & isLegallySeparated(X)
    Implies: NotConsideredMarried(Taxpayer)
  - A married individual who files a separate return, maintains a household for a child, and whose spouse is not a member of the household for the last 6 months is not considered married.
    FOL: isTaxpayer(X) & isMarried(X) & isNotJointReturn(X, true) & maintainsHousehold(X, H) & hasChild(X, Y) & hasDeduction(X, DED)
    Implies: NotConsideredMarried(Taxpayer)
  - A taxpayer with a dependent is allowed a deduction for personal exemptions for that dependent.
    FOL: isTaxpayer(X) & hasDependent(X, Y) & isDependent(Y)
    Implies: AllowedDeductionForDependent(Taxpayer)
  - A qualifying child of a taxpayer is a dependent.
    FOL: isQualifyingChild(X)
    Implies: IsDependent(Person)
  - A qualifying relative of a taxpayer is a dependent.
    FOL: isQualifyingRelative(X)
    Implies: IsDependent(Person)
  - A taxpayer with adjusted gross income and itemized deductions is subject to the overall limitation on itemized deductions.
    FOL: isTaxpayer(X) & hasAdjustedGrossIncome(X, I) & hasItemizedDeductions(X, D)
    Implies: SubjectToItemizedDeductionLimitation(Taxpayer)

Options:
1. Approve (type 'approve')
2. Provide feedback for improvements (type your feedback)

```

## 最终TBox（完整）

```json
{
  "classes": [
    {
      "name": "Person",
      "description": "An individual human being, including taxpayers, spouses, dependents, employees, and employers."
    },
    {
      "name": "Employer",
      "description": "A person who employs individuals and pays wages, subject to excise tax under §3301."
    },
    {
      "name": "Employee",
      "description": "An individual who performs services for an employer and receives remuneration."
    },
    {
      "name": "Taxpayer",
      "description": "An individual subject to income tax under §1, including married individuals, surviving spouses, heads of households, and unmarried individuals."
    },
    {
      "name": "Spouse",
      "description": "A married individual's partner, relevant for filing status and exemptions."
    },
    {
      "name": "Dependent",
      "description": "An individual who qualifies as a dependent under §152, including qualifying children and qualifying relatives."
    },
    {
      "name": "QualifyingChild",
      "description": "A child who meets the relationship, abode, age, and joint return tests under §152(c)."
    },
    {
      "name": "QualifyingRelative",
      "description": "An individual who meets the relationship, income, and dependency tests under §152(d)."
    },
    {
      "name": "SurvivingSpouse",
      "description": "A taxpayer whose spouse died in one of the two preceding years and who maintains a household for a dependent child, as defined in §2(a)."
    },
    {
      "name": "HeadOfHousehold",
      "description": "An individual who is not married or a surviving spouse and maintains a household for a qualifying child or dependent, as defined in §2(b)."
    },
    {
      "name": "Wages",
      "description": "All remuneration for employment, including cash and non-cash benefits, subject to exceptions under §3306(b)."
    },
    {
      "name": "Employment",
      "description": "Any service performed by an employee for an employer, subject to exceptions under §3306(c)."
    },
    {
      "name": "TaxableIncome",
      "description": "Gross income minus deductions (other than standard deduction) or adjusted gross income minus standard deduction and personal exemptions, as defined in §63."
    },
    {
      "name": "GrossIncome",
      "description": "Total income from all sources before deductions."
    },
    {
      "name": "AdjustedGrossIncome",
      "description": "Gross income minus certain deductions (above-the-line), used in §63(b) and §68."
    },
    {
      "name": "Deduction",
      "description": "An amount allowed as a deduction from gross income or adjusted gross income, including standard and itemized deductions."
    },
    {
      "name": "StandardDeduction",
      "description": "The sum of the basic standard deduction and additional standard deduction under §63(c)."
    },
    {
      "name": "ItemizedDeductions",
      "description": "Deductions allowable under this chapter other than those in arriving at adjusted gross income and personal exemptions, as defined in §63(d)."
    },
    {
      "name": "PersonalExemption",
      "description": "An exemption amount allowed as a deduction for the taxpayer, spouse, and dependents under §151."
    },
    {
      "name": "TaxableYear",
      "description": "The calendar year or fiscal year for which tax is determined."
    },
    {
      "name": "CalendarYear",
      "description": "A period of 12 months from January 1 to December 31."
    },
    {
      "name": "FilingStatus",
      "description": "The category under which a taxpayer files a return: married filing jointly, surviving spouse, head of household, unmarried individual, or married filing separately."
    },
    {
      "name": "TaxRateBracket",
      "description": "A range of taxable income with a corresponding tax rate and base amount, as specified in §1."
    },
    {
      "name": "Household",
      "description": "A home maintained by a taxpayer, used in determining head of household and surviving spouse status."
    }
  ],
  "properties": [
    {
      "type": "unary",
      "name": "isEmployer",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is an employer as defined in §3306(a)."
    },
    {
      "type": "unary",
      "name": "isNotEmployer",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not an employer."
    },
    {
      "type": "unary",
      "name": "isEmployee",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is an employee."
    },
    {
      "type": "unary",
      "name": "isNotEmployee",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not an employee."
    },
    {
      "type": "unary",
      "name": "isTaxpayer",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is a taxpayer."
    },
    {
      "type": "unary",
      "name": "isNotTaxpayer",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not a taxpayer."
    },
    {
      "type": "unary",
      "name": "isDependent",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is a dependent under §152."
    },
    {
      "type": "unary",
      "name": "isNotDependent",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not a dependent."
    },
    {
      "type": "unary",
      "name": "isQualifyingChild",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is a qualifying child under §152(c)."
    },
    {
      "type": "unary",
      "name": "isNotQualifyingChild",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not a qualifying child."
    },
    {
      "type": "unary",
      "name": "isQualifyingRelative",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is a qualifying relative under §152(d)."
    },
    {
      "type": "unary",
      "name": "isNotQualifyingRelative",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not a qualifying relative."
    },
    {
      "type": "unary",
      "name": "isSurvivingSpouse",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is a surviving spouse under §2(a)."
    },
    {
      "type": "unary",
      "name": "isNotSurvivingSpouse",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not a surviving spouse."
    },
    {
      "type": "unary",
      "name": "isHeadOfHousehold",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is a head of household under §2(b)."
    },
    {
      "type": "unary",
      "name": "isNotHeadOfHousehold",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not a head of household."
    },
    {
      "type": "unary",
      "name": "isMarried",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is married as determined under §7703."
    },
    {
      "type": "unary",
      "name": "isNotMarried",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not married."
    },
    {
      "type": "unary",
      "name": "isBlind",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is blind at the close of the taxable year."
    },
    {
      "type": "unary",
      "name": "isNotBlind",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not blind."
    },
    {
      "type": "unary",
      "name": "isAged",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person has attained age 65 before the close of the taxable year."
    },
    {
      "type": "unary",
      "name": "isNotAged",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person has not attained age 65."
    },
    {
      "type": "unary",
      "name": "isNonresidentAlien",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is a nonresident alien."
    },
    {
      "type": "unary",
      "name": "isNotNonresidentAlien",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not a nonresident alien."
    },
    {
      "type": "unary",
      "name": "isLegallySeparated",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is legally separated under a decree of divorce or separate maintenance."
    },
    {
      "type": "unary",
      "name": "isNotLegallySeparated",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not legally separated."
    },
    {
      "type": "unary",
      "name": "isCommittedToPenalInstitution",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is committed to a penal institution."
    },
    {
      "type": "unary",
      "name": "isNotCommittedToPenalInstitution",
      "arguments": [
        "Person"
      ],
      "description": "Indicates whether a person is not committed to a penal institution."
    },
    {
      "type": "object",
      "name": "hasSpouse",
      "arguments": [
        "Person",
        "Person"
      ],
      "description": "Relates a person to their spouse."
    },
    {
      "type": "object",
      "name": "hasEmployer",
      "arguments": [
        "Person",
        "Person"
      ],
      "description": "Relates an employee to their employer."
    },
    {
      "type": "object",
      "name": "hasEmployee",
      "arguments": [
        "Person",
        "Person"
      ],
      "description": "Relates an employer to an employee."
    },
    {
      "type": "object",
      "name": "hasDependent",
      "arguments": [
        "Person",
        "Person"
      ],
      "description": "Relates a taxpayer to a dependent."
    },
    {
      "type": "object",
      "name": "isDependentOf",
      "arguments": [
        "Person",
        "Person"
      ],
      "description": "Relates a dependent to the taxpayer claiming them."
    },
    {
      "type": "object",
      "name": "hasChild",
      "arguments": [
        "Person",
        "Person"
      ],
      "description": "Relates a person to their child."
    },
    {
      "type": "object",
      "name": "hasParent",
      "arguments": [
        "Person",
        "Person"
      ],
      "description": "Relates a person to their parent."
    },
    {
      "type": "object",
      "name": "maintainsHousehold",
      "arguments": [
        "Person",
        "Household"
      ],
      "description": "Relates a person to a household they maintain."
    },
    {
      "type": "object",
      "name": "hasPrincipalPlaceOfAbode",
      "arguments": [
        "Person",
        "Household"
      ],
      "description": "Relates a person to their principal place of abode."
    },
    {
      "type": "object",
      "name": "hasFilingStatus",
      "arguments": [
        "Person",
        "FilingStatus"
      ],
      "description": "Relates a taxpayer to their filing status."
    },
    {
      "type": "object",
      "name": "hasTaxableYear",
      "arguments": [
        "Person",
        "TaxableYear"
      ],
      "description": "Relates a taxpayer to their taxable year."
    },
    {
      "type": "object",
      "name": "hasWages",
      "arguments": [
        "Person",
        "Wages"
      ],
      "description": "Relates an employee to wages received."
    },
    {
      "type": "object",
      "name": "hasEmployment",
      "arguments": [
        "Person",
        "Employment"
      ],
      "description": "Relates an employee to an employment relationship."
    },
    {
      "type": "object",
      "name": "hasGrossIncome",
      "arguments": [
        "Person",
        "GrossIncome"
      ],
      "description": "Relates a taxpayer to their gross income."
    },
    {
      "type": "object",
      "name": "hasAdjustedGrossIncome",
      "arguments": [
        "Person",
        "AdjustedGrossIncome"
      ],
      "description": "Relates a taxpayer to their adjusted gross income."
    },
    {
      "type": "object",
      "name": "hasTaxableIncome",
      "arguments": [
        "Person",
        "TaxableIncome"
      ],
      "description": "Relates a taxpayer to their taxable income."
    },
    {
      "type": "object",
      "name": "hasDeduction",
      "arguments": [
        "Person",
        "Deduction"
      ],
      "description": "Relates a taxpayer to a deduction."
    },
    {
      "type": "object",
      "name": "hasStandardDeduction",
      "arguments": [
        "Person",
        "StandardDeduction"
      ],
      "description": "Relates a taxpayer to their standard deduction."
    },
    {
      "type": "object",
      "name": "hasItemizedDeductions",
      "arguments": [
        "Person",
        "ItemizedDeductions"
      ],
      "description": "Relates a taxpayer to their itemized deductions."
    },
    {
      "type": "object",
      "name": "hasPersonalExemption",
      "arguments": [
        "Person",
        "PersonalExemption"
      ],
      "description": "Relates a taxpayer to a personal exemption."
    },
    {
      "type": "object",
      "name": "hasTaxRateBracket",
      "arguments": [
        "FilingStatus",
        "TaxRateBracket"
      ],
      "description": "Relates a filing status to applicable tax rate brackets."
    },
    {
      "type": "datatype",
      "name": "wageAmount",
      "arguments": [
        "Wages",
        "decimal"
      ],
      "description": "The monetary amount of wages."
    },
    {
      "type": "datatype",
      "name": "grossIncomeAmount",
      "arguments": [
        "GrossIncome",
        "decimal"
      ],
      "description": "The monetary amount of gross income."
    },
    {
      "type": "datatype",
      "name": "adjustedGrossIncomeAmount",
      "arguments": [
        "AdjustedGrossIncome",
        "decimal"
      ],
      "description": "The monetary amount of adjusted gross income."
    },
    {
      "type": "datatype",
      "name": "taxableIncomeAmount",
      "arguments": [
        "TaxableIncome",
        "decimal"
      ],
      "description": "The monetary amount of taxable income."
    },
    {
      "type": "datatype",
      "name": "deductionAmount",
      "arguments": [
        "Deduction",
        "decimal"
      ],
      "description": "The monetary amount of a deduction."
    },
    {
      "type": "datatype",
      "name": "standardDeductionAmount",
      "arguments": [
        "StandardDeduction",
        "decimal"
      ],
      "description": "The monetary amount of the standard deduction."
    },
    {
      "type": "datatype",
      "name": "itemizedDeductionAmount",
      "arguments": [
        "ItemizedDeductions",
        "decimal"
      ],
      "description": "The monetary amount of itemized deductions."
    },
    {
      "type": "datatype",
      "name": "exemptionAmount",
      "arguments": [
        "PersonalExemption",
        "decimal"
      ],
      "description": "The monetary amount of a personal exemption."
    },
    {
      "type": "datatype",
      "name": "bracketThreshold",
      "arguments": [
        "TaxRateBracket",
        "decimal"
      ],
      "description": "The upper income threshold for a tax rate bracket."
    },
    {
      "type": "datatype",
      "name": "bracketRate",
      "arguments": [
        "TaxRateBracket",
        "decimal"
      ],
      "description": "The tax rate for a bracket, expressed as a decimal."
    },
    {
      "type": "datatype",
      "name": "bracketBaseAmount",
      "arguments": [
        "TaxRateBracket",
        "decimal"
      ],
      "description": "The base tax amount for a bracket."
    },
    {
      "type": "datatype",
      "name": "taxYear",
      "arguments": [
        "TaxableYear",
        "integer"
      ],
      "description": "The year of the taxable year."
    },
    {
      "type": "datatype",
      "name": "dateOfBirth",
      "arguments": [
        "Person",
        "string"
      ],
      "description": "The date of birth of a person, represented as an ISO 8601 string."
    },
    {
      "type": "datatype",
      "name": "dateOfDeath",
      "arguments": [
        "Person",
        "string"
      ],
      "description": "The date of death of a person, represented as an ISO 8601 string."
    },
    {
      "type": "datatype",
      "name": "dateOfMarriage",
      "arguments": [
        "Person",
        "string"
      ],
      "description": "The date a person got married, represented as an ISO 8601 string."
    },
    {
      "type": "datatype",
      "name": "numberOfEmployees",
      "arguments": [
        "Person",
        "integer"
      ],
      "description": "The number of employees employed by an employer."
    },
    {
      "type": "datatype",
      "name": "numberOfDaysEmployed",
      "arguments": [
        "Person",
        "integer"
      ],
      "description": "The number of days on which an employer employed at least one individual."
    },
    {
      "type": "datatype",
      "name": "householdMaintenanceCost",
      "arguments": [
        "Household",
        "decimal"
      ],
      "description": "The cost of maintaining a household."
    },
    {
      "type": "datatype",
      "name": "isJointReturn",
      "arguments": [
        "Person",
        "boolean"
      ],
      "description": "Indicates whether a taxpayer files a joint return."
    },
    {
      "type": "datatype",
      "name": "isNotJointReturn",
      "arguments": [
        "Person",
        "boolean"
      ],
      "description": "Indicates whether a taxpayer does not file a joint return."
    },
    {
      "type": "datatype",
      "name": "itemizesDeductions",
      "arguments": [
        "Person",
        "boolean"
      ],
      "description": "Indicates whether a taxpayer elects to itemize deductions."
    },
    {
      "type": "datatype",
      "name": "doesNotItemizeDeductions",
      "arguments": [
        "Person",
        "boolean"
      ],
      "description": "Indicates whether a taxpayer does not elect to itemize deductions."
    }
  ],
  "rules": [
    {
      "fol_expression": "isEmployer(X) & hasEmployee(X, Y)",
      "implication_property_type": "unary",
      "implication_property_name": "SubjectToExciseTax",
      "implication_property_arguments": [
        "Employer"
      ],
      "description": "An employer that has individuals in employment is subject to an excise tax with respect to having individuals in employ."
    },
    {
      "fol_expression": "isMarried(X) & isJointReturn(X, true)",
      "implication_property_type": "unary",
      "implication_property_name": "QualifiesForJointFilingStatus",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A married individual who files a joint return qualifies for joint filing status."
    },
    {
      "fol_expression": "isSurvivingSpouse(X)",
      "implication_property_type": "unary",
      "implication_property_name": "QualifiesForJointFilingStatus",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A surviving spouse qualifies for joint filing status."
    },
    {
      "fol_expression": "isHeadOfHousehold(X)",
      "implication_property_type": "unary",
      "implication_property_name": "QualifiesForHeadOfHouseholdStatus",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A head of household qualifies for head of household filing status."
    },
    {
      "fol_expression": "isTaxpayer(X) & isNotMarried(X) & isNotSurvivingSpouse(X) & isNotHeadOfHousehold(X)",
      "implication_property_type": "unary",
      "implication_property_name": "QualifiesForSingleFilingStatus",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "An individual who is not a married individual, not a surviving spouse, and not a head of household qualifies for single filing status."
    },
    {
      "fol_expression": "isMarried(X) & isNotJointReturn(X, true)",
      "implication_property_type": "unary",
      "implication_property_name": "QualifiesForMarriedFilingSeparatelyStatus",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A married individual who does not file a joint return qualifies for married filing separately status."
    },
    {
      "fol_expression": "isTaxpayer(X) & doesNotItemizeDeductions(X, true)",
      "implication_property_type": "unary",
      "implication_property_name": "UsesStandardDeduction",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A taxpayer who does not elect to itemize deductions uses the standard deduction."
    },
    {
      "fol_expression": "isTaxpayer(X) & isAged(X)",
      "implication_property_type": "unary",
      "implication_property_name": "EntitledToAdditionalStandardDeduction",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A taxpayer who is aged is entitled to an additional standard deduction."
    },
    {
      "fol_expression": "isTaxpayer(X) & isBlind(X)",
      "implication_property_type": "unary",
      "implication_property_name": "EntitledToAdditionalStandardDeduction",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A taxpayer who is blind is entitled to an additional standard deduction."
    },
    {
      "fol_expression": "isTaxpayer(X) & hasSpouse(X, Y) & isAged(Y)",
      "implication_property_type": "unary",
      "implication_property_name": "EntitledToAdditionalStandardDeductionForSpouse",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A taxpayer whose spouse is aged is entitled to an additional standard deduction for the spouse."
    },
    {
      "fol_expression": "isTaxpayer(X) & hasSpouse(X, Y) & isBlind(Y)",
      "implication_property_type": "unary",
      "implication_property_name": "EntitledToAdditionalStandardDeductionForSpouse",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A taxpayer whose spouse is blind is entitled to an additional standard deduction for the spouse."
    },
    {
      "fol_expression": "isTaxpayer(X) & hasSpouse(X, Y) & dateOfDeath(Y, D) & maintainsHousehold(X, H) & hasChild(X, Z) & isDependent(Z) & hasDeduction(X, DED)",
      "implication_property_type": "unary",
      "implication_property_name": "IsSurvivingSpouse",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A taxpayer whose spouse died in the preceding two years, who maintains a household for a dependent child, and is entitled to a deduction for the child is a surviving spouse."
    },
    {
      "fol_expression": "isTaxpayer(X) & isNotMarried(X) & isNotSurvivingSpouse(X) & maintainsHousehold(X, H) & hasChild(X, Y) & isQualifyingChild(Y)",
      "implication_property_type": "unary",
      "implication_property_name": "IsHeadOfHousehold",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "An individual who is not married, not a surviving spouse, and maintains a household for a qualifying child is a head of household."
    },
    {
      "fol_expression": "isTaxpayer(X) & isNotMarried(X) & isNotSurvivingSpouse(X) & maintainsHousehold(X, H) & hasDependent(X, Y) & isDependent(Y)",
      "implication_property_type": "unary",
      "implication_property_name": "IsHeadOfHousehold",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "An individual who is not married, not a surviving spouse, and maintains a household for a dependent is a head of household."
    },
    {
      "fol_expression": "isTaxpayer(X) & isNotMarried(X) & isNotSurvivingSpouse(X) & maintainsHousehold(X, H) & hasParent(X, Y) & hasDeduction(X, DED)",
      "implication_property_type": "unary",
      "implication_property_name": "IsHeadOfHousehold",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "An individual who is not married, not a surviving spouse, and maintains a household for a parent for whom the taxpayer is entitled to a deduction is a head of household."
    },
    {
      "fol_expression": "isTaxpayer(X) & isLegallySeparated(X)",
      "implication_property_type": "unary",
      "implication_property_name": "NotConsideredMarried",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "An individual who is legally separated under a decree of divorce or separate maintenance is not considered married."
    },
    {
      "fol_expression": "isTaxpayer(X) & isMarried(X) & isNotJointReturn(X, true) & maintainsHousehold(X, H) & hasChild(X, Y) & hasDeduction(X, DED)",
      "implication_property_type": "unary",
      "implication_property_name": "NotConsideredMarried",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A married individual who files a separate return, maintains a household for a child, and whose spouse is not a member of the household for the last 6 months is not considered married."
    },
    {
      "fol_expression": "isTaxpayer(X) & hasDependent(X, Y) & isDependent(Y)",
      "implication_property_type": "unary",
      "implication_property_name": "AllowedDeductionForDependent",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A taxpayer with a dependent is allowed a deduction for personal exemptions for that dependent."
    },
    {
      "fol_expression": "isQualifyingChild(X)",
      "implication_property_type": "unary",
      "implication_property_name": "IsDependent",
      "implication_property_arguments": [
        "Person"
      ],
      "description": "A qualifying child of a taxpayer is a dependent."
    },
    {
      "fol_expression": "isQualifyingRelative(X)",
      "implication_property_type": "unary",
      "implication_property_name": "IsDependent",
      "implication_property_arguments": [
        "Person"
      ],
      "description": "A qualifying relative of a taxpayer is a dependent."
    },
    {
      "fol_expression": "isTaxpayer(X) & hasAdjustedGrossIncome(X, I) & hasItemizedDeductions(X, D)",
      "implication_property_type": "unary",
      "implication_property_name": "SubjectToItemizedDeductionLimitation",
      "implication_property_arguments": [
        "Taxpayer"
      ],
      "description": "A taxpayer with adjusted gross income and itemized deductions is subject to the overall limitation on itemized deductions."
    }
  ]
}
```
