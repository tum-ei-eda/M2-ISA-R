// Rule DescriptionContent
ruleDescriptionContent:
	ruleImport
	*
	ruleISA
	+
;

// Rule Import
ruleImport:
	'import'
	RULE_STRING
;

// Rule ISA
ruleISA:
	(
		ruleInstructionSet
		    |
		ruleCoreDef
	)
;

// Rule InstructionSet
ruleInstructionSet:
	'InstructionSet'
	RULE_ID
	(
		'extends'
		RULE_ID
	)?
	'{'
	(
		ruleSectionArchState
		(
			ruleSectionFunctions
			ruleSectionInstructions?
			    |
			ruleSectionInstructions
		)?
		    |
		ruleSectionFunctions
		(
			ruleSectionArchState
			ruleSectionInstructions?
			    |
			ruleSectionInstructions
		)?
		    |
		ruleSectionInstructions
		(
			ruleSectionArchState
			ruleSectionFunctions?
			    |
			ruleSectionFunctions
		)?
	)
	'}'
;

// Rule CoreDef
ruleCoreDef:
	'Core'
	RULE_ID
	(
		'provides'
		RULE_ID
		(
			','
			RULE_ID
		)*
	)?
	'{'
	(
		ruleSectionArchState
		(
			ruleSectionFunctions
			ruleSectionInstructions?
			    |
			ruleSectionInstructions
		)?
		    |
		ruleSectionFunctions
		(
			ruleSectionArchState
			ruleSectionInstructions?
			    |
			ruleSectionInstructions
		)?
		    |
		ruleSectionInstructions
		(
			ruleSectionArchState
			ruleSectionFunctions?
			    |
			ruleSectionFunctions
		)?
	)
	'}'
;

// Rule SectionArchState
ruleSectionArchState:
	'architectural_state'
	'{'
	(
		ruleDeclaration
		    |ruleExpressionStatement
	)+
	'}'
;

// Rule SectionFunctions
ruleSectionFunctions:
	'functions'
	'{'
	ruleFunctionDefinition
	+
	'}'
;

// Rule SectionInstructions
ruleSectionInstructions:
	'instructions'
	ruleAttribute
	*
	'{'
	ruleInstruction
	+
	'}'
;

// Rule Instruction
ruleInstruction:
	RULE_ID
	ruleAttribute
	*
	'{'
	'encoding'
	':'
	ruleEncoding
	';'
	(
		'args_disass'
		':'
		RULE_STRING
		';'
	)?
	'behavior'
	':'
	ruleStatement
	'}'
;

// Rule Encoding
ruleEncoding:
	ruleField
	(
		'::'
		ruleField
	)*
;

// Rule Field
ruleField:
	(
		ruleBitValue
		    |
		ruleBitField
	)
;

// Rule BitValue
ruleBitValue:
	RULE_INTEGER
;

// Rule BitField
ruleBitField:
	RULE_ID
	RULE_LEFT_BR
	ruleIntegerConstant
	':'
	ruleIntegerConstant
	RULE_RIGHT_BR
;

// Rule FunctionDefinition
ruleFunctionDefinition:
	(
		'extern'
		ruleTypeSpecifier
		RULE_ID
		'('
		ruleParameterList?
		')'
		';'
		    |
		ruleTypeSpecifier
		RULE_ID
		'('
		ruleParameterList?
		')'
		ruleAttribute
		*
		ruleCompoundStatement
	)
;

// Rule ParameterList
ruleParameterList:
	ruleParameterDeclaration
	(
		','
		ruleParameterDeclaration
	)*
;

// Rule ParameterDeclaration
ruleParameterDeclaration:
	ruleTypeSpecifier
	(
		ruleDirectDeclarator
		    |
		ruleAbstractDeclarator
	)?
;

// Rule Statement
ruleStatement:
	(
		ruleCompoundStatement
		    |
		ruleExpressionStatement
		    |
		ruleSelectionStatement
		    |
		ruleIterationStatement
		    |
		ruleJumpStatement
		    |
		ruleSpawnStatement
	)
;

// Rule LabeledStatement
ruleLabeledStatement:
	(
		'case'
		ruleConstantExpression
		':'
		ruleStatement
		*
		    |
		'default'
		':'
		ruleStatement
		*
	)
;

// Rule CompoundStatement
ruleCompoundStatement:
	'{'
	ruleBlockItem
	*
	'}'
;

// Rule BlockItem
ruleBlockItem:
	(
		ruleStatement
		    |
		ruleDeclaration
	)
;

// Rule ExpressionStatement
ruleExpressionStatement:
	ruleExpressionList
	?
	';'
;

// Rule SelectionStatement
ruleSelectionStatement:
	(
		ruleIfStatement
		    |
		ruleSwitchStatement
	)
;

// Rule IfStatement
ruleIfStatement:
	'if'
	'('
	ruleConditionalExpression
	')'
	ruleStatement
	(
		(
			('else')=>
			'else'
		)
		ruleStatement
	)?
;

// Rule SwitchStatement
ruleSwitchStatement:
	'switch'
	'('
	ruleConditionalExpression
	')'
	'{'
	ruleLabeledStatement
	+
	'}'
;

// Rule IterationStatement
ruleIterationStatement:
	(
		'while'
		'('
		ruleConditionalExpression
		')'
		ruleStatement
		    |
		'do'
		ruleStatement
		'while'
		'('
		ruleConditionalExpression
		')'
		';'
		    |
		'for'
		'('
		ruleForCondition
		')'
		ruleStatement
	)
;

// Rule ForCondition
ruleForCondition:
	(
		ruleDeclaration
		    |
		ruleAssignmentExpression
		?
		';'
	)
	ruleConditionalExpression
	?
	';'
	(
		ruleAssignmentExpression
		(
			','
			ruleAssignmentExpression
		)*
	)?
;

// Rule JumpStatement
ruleJumpStatement:
	(
		'continue'
		';'
		    |
		'break'
		';'
		    |
		'return'
		ruleConditionalExpression
		?
		';'
	)
;

// Rule SpawnStatement
ruleSpawnStatement:
	'spawn'
	ruleStatement
;

// Rule Declaration
ruleDeclaration:
	ruleDeclarationSpecifier*
	ruleTypeSpecifier
	(
		'*'
		    |
		'&'
	)?
	(
		ruleInitDeclarator
		(
			','
			ruleInitDeclarator
		)*
	)?
	';'
;

// Rule DeclarationSpecifier
ruleDeclarationSpecifier:
	(
		ruleStorageClassSpecifier
		    |
		ruleTypeQualifier
		    |
		ruleAttribute
	)
;

// Rule Attribute
ruleAttribute:
	ruleDoubleLeftBracket
	ruleAttributeName
	(
		'='
		ruleConditionalExpression
	)?
	ruleDoubleRightBracket
;

// Rule TypeSpecifier
ruleTypeSpecifier:
	(
		rulePrimitiveType
		    |
		ruleCompositeType
		    |
		ruleEnumType
	)
;

// Rule PrimitiveType
rulePrimitiveType:
	ruleDataTypes
	+
	ruleBitSizeSpecifier?
;

// Rule BitSizeSpecifier
ruleBitSizeSpecifier:
	'<'
	rulePrimaryExpression
	(
		','
		rulePrimaryExpression
		','
		rulePrimaryExpression
		','
		rulePrimaryExpression
	)?
	'>'
;

// Rule EnumType
ruleEnumType:
	(
		'enum'
		RULE_ID
		?
		'{'
		ruleEnumeratorList
		','?
		'}'
		    |
		'enum'
		RULE_ID
	)
;

// Rule EnumeratorList
ruleEnumeratorList:
	ruleEnumerator
	(
		','
		ruleEnumerator
	)*
;

// Rule Enumerator
ruleEnumerator:
	(
		RULE_ID
		    |
		RULE_ID
		'='
		ruleConstantExpression
	)
;

// Rule CompositeType
ruleCompositeType:
	(
		ruleStructOrUnion
		RULE_ID
		?
		'{'
		ruleStructDeclaration
		*
		'}'
		    |
		ruleStructOrUnion
		RULE_ID
	)
;

// Rule StructDeclaration
ruleStructDeclaration:
	ruleStructDeclarationSpecifier
	ruleDirectDeclarator
	(
		','
		ruleDirectDeclarator
	)*
	';'
;

// Rule StructDeclarationSpecifier
ruleStructDeclarationSpecifier:
	(
		ruleTypeSpecifier
		    |
		ruleTypeQualifier
	)
;

// Rule InitDeclarator
ruleInitDeclarator:
	ruleDirectDeclarator
	ruleAttribute
	*
	(
		'='
		ruleInitializer
	)?
;

// Rule DirectDeclarator
ruleDirectDeclarator:
	RULE_ID
	(
		':'
		ruleIntegerConstant
	)?
	(
		(
			RULE_LEFT_BR
			ruleConditionalExpression
			RULE_RIGHT_BR
		)+
		    |
		'('
		ruleParameterList
		')'
	)?
;

// Rule Initializer
ruleInitializer:
	(
		ruleConditionalExpression
		    |
		'{'
		ruleInitializerList
		','?
		'}'
	)
;

// Rule InitializerList
ruleInitializerList:
	(
		ruleDesignatedInitializer
		    |ruleInitializer
	)
	(
		','
		(
			ruleDesignatedInitializer
			    |ruleInitializer
		)
	)*
;

// Rule DesignatedInitializer
ruleDesignatedInitializer:
	ruleDesignator
	+
	'='
	ruleInitializer
;

// Rule Designator
ruleDesignator:
	(
		RULE_LEFT_BR
		ruleConstantExpression
		RULE_RIGHT_BR
		    |
		'.'
		RULE_ID
	)
;

// Rule AbstractDeclarator
ruleAbstractDeclarator:
	ruleDirectAbstractDeclarator
;

// Rule DirectAbstractDeclarator
ruleDirectAbstractDeclarator:
	(
		'('
		(
			ruleAbstractDeclarator
			?
			    |
			ruleParameterList
		)
		')'
		    |
		RULE_LEFT_BR
		ruleConstantExpression
		?
		RULE_RIGHT_BR
	)
;

// Rule ExpressionList
ruleExpressionList:
	ruleAssignmentExpression
	(
		','
		ruleAssignmentExpression
	)*
;

// Rule AssignmentExpression
ruleAssignmentExpression:
	rulePrefixExpression
	(
		ruleAssignment
	)*
;

// Rule Assignment
ruleAssignment:
	(
		'='
		    |
		'*='
		    |
		'/='
		    |
		'%='
		    |
		'+='
		    |
		'-='
		    |
		'<<='
		    |
		'>>='
		    |
		'&='
		    |
		'^='
		    |
		'|='
	)
	ruleConditionalExpression
;

// Rule ConditionalExpression
ruleConditionalExpression:
	ruleConcatenationExpression
	(
		'?'
		ruleConditionalExpression
		':'
		ruleConditionalExpression
	)?
;

// Rule ConcatenationExpression
ruleConcatenationExpression:
	ruleLogicalOrExpression
	(
		'::'
		ruleConcatenationExpression
	)?
;

// Rule LogicalOrExpression
ruleLogicalOrExpression:
	ruleLogicalAndExpression
	(
		'||'
		ruleLogicalOrExpression
	)?
;

// Rule LogicalAndExpression
ruleLogicalAndExpression:
	ruleInclusiveOrExpression
	(
		'&&'
		ruleLogicalAndExpression
	)?
;

// Rule InclusiveOrExpression
ruleInclusiveOrExpression:
	ruleExclusiveOrExpression
	(
		'|'
		ruleInclusiveOrExpression
	)?
;

// Rule ExclusiveOrExpression
ruleExclusiveOrExpression:
	ruleAndExpression
	(
		'^'
		ruleExclusiveOrExpression
	)?
;

// Rule AndExpression
ruleAndExpression:
	ruleEqualityExpression
	(
		'&'
		ruleAndExpression
	)?
;

// Rule EqualityExpression
ruleEqualityExpression:
	ruleRelationalExpression
	(
		(
			'=='
			    |
			'!='
		)
		ruleEqualityExpression
	)?
;

// Rule RelationalExpression
ruleRelationalExpression:
	ruleShiftExpression
	(
		(
			'<'
			    |
			'>'
			    |
			'<='
			    |
			'>='
		)
		ruleRelationalExpression
	)?
;

// Rule ShiftExpression
ruleShiftExpression:
	ruleAdditiveExpression
	(
		(
			'<<'
			    |
			'>>'
		)
		ruleShiftExpression
	)?
;

// Rule AdditiveExpression
ruleAdditiveExpression:
	ruleMultiplicativeExpression
	(
		(
			'+'
			    |
			'-'
		)
		ruleAdditiveExpression
	)?
;

// Rule MultiplicativeExpression
ruleMultiplicativeExpression:
	ruleCastExpression
	(
		(
			'*'
			    |
			'/'
			    |
			'%'
		)
		ruleMultiplicativeExpression
	)?
;

// Rule CastExpression
ruleCastExpression:
	(
		rulePrefixExpression
		    |
		'('
		ruleTypeSpecifier
		')'
		ruleCastExpression
	)
;

// Rule PrefixExpression
rulePrefixExpression:
	(
		rulePostfixExpression
		    |
		'++'
		rulePrefixExpression
		    |
		'--'
		rulePrefixExpression
		    |
		ruleUnaryOperator
		ruleCastExpression
		    |
		'sizeof'
		'('
		(
			rulePostfixExpression
			    |
			ruleTypeSpecifier
		)
		')'
	)
;

// Rule UnaryOperator
ruleUnaryOperator:
	(
		'&'
		    |
		'*'
		    |
		'+'
		    |
		'-'
		    |
		'~'
		    |
		'!'
	)
;

// Rule PostfixExpression
rulePostfixExpression:
	rulePrimaryExpression
	(
		rulePostfix
	)?
;

// Rule Postfix
rulePostfix:
	(
		RULE_LEFT_BR
		ruleConditionalExpression
		(
			':'
			ruleConditionalExpression
		)?
		RULE_RIGHT_BR
		    |
		'('
		(
			ruleConditionalExpression
			(
				','
				ruleConditionalExpression
			)*
		)?
		')'
		    |
		'.'
		RULE_ID
		    |
		'->'
		RULE_ID
		    |
		'++'
		    |
		'--'
	)
	rulePostfix
	?
;

// Rule PrimaryExpression
rulePrimaryExpression:
	(
		RULE_ID
		    |
		ruleConstant
		    |
		ruleStringLiteral
		+
		    |
		'('
		ruleConditionalExpression
		')'
	)
;

// Rule StringLiteral
ruleStringLiteral:
	(
		RULE_ENCSTRINGCONST
		    |
		RULE_STRING
	)
;

// Rule ConstantExpression
ruleConstantExpression:
	ruleConditionalExpression
;

// Rule Constant
ruleConstant:
	(
		ruleIntegerConstant
		    |
		ruleFloatingConstant
		    |
		ruleCharacterConstant
		    |
		ruleBoolConstant
	)
;

// Rule IntegerConstant
ruleIntegerConstant:
	RULE_INTEGER
;

// Rule FloatingConstant
ruleFloatingConstant:
	RULE_FLOAT
;

// Rule BoolConstant
ruleBoolConstant:
	RULE_BOOLEAN
;

// Rule CharacterConstant
ruleCharacterConstant:
	RULE_CHARCONST
;

// Rule DoubleLeftBracket
ruleDoubleLeftBracket:
	RULE_LEFT_BR
	RULE_LEFT_BR
;

// Rule DoubleRightBracket
ruleDoubleRightBracket:
	RULE_RIGHT_BR
	RULE_RIGHT_BR
;

// Rule DataTypes
ruleDataTypes:
	(
		'bool'
		    |
		'char'
		    |
		'short'
		    |
		'int'
		    |
		'long'
		    |
		'signed'
		    |
		'unsigned'
		    |
		'float'
		    |
		'double'
		    |
		'void'
		    |
		'alias'
	)
;

// Rule TypeQualifier
ruleTypeQualifier:
	(
		'const'
		    |
		'volatile'
	)
;

// Rule StorageClassSpecifier
ruleStorageClassSpecifier:
	(
		'extern'
		    |
		'static'
		    |
		'register'
	)
;

// Rule AttributeName
ruleAttributeName:
	(
		'NONE'
		    |
		'is_pc'
		    |
		'is_interlock_for'
		    |
		'do_not_synthesize'
		    |
		'enable'
		    |
		'no_cont'
		    |
		'cond'
		    |
		'flush'
	)
;

// Rule StructOrUnion
ruleStructOrUnion:
	(
		'struct'
		    |
		'union'
	)
;

RULE_LEFT_BR : '[';

RULE_RIGHT_BR : ']';

RULE_BOOLEAN : ('true'|'false');

RULE_FLOAT : ('0'..'9')+ '.' ('0'..'9')* (('e'|'E') ('+'|'-')? ('0'..'9')+)? ('f'|'F'|'l'|'L')?;

RULE_INTEGER : (RULE_BINARYINT|RULE_HEXADECIMALINT|RULE_OCTALINT|RULE_DECIMALINT|RULE_VLOGINT) ('u'|'U')? (('l'|'L') ('l'|'L')?)?;

fragment RULE_BINARYINT : ('0b'|'0B') '0'..'1' ('_'? '0'..'1')*;

fragment RULE_OCTALINT : '0' '_'? '0'..'7' ('_'? '0'..'7')*;

fragment RULE_DECIMALINT : ('0'|'1'..'9' ('_'? '0'..'9')*);

fragment RULE_HEXADECIMALINT : ('0x'|'0X') ('0'..'9'|'a'..'f'|'A'..'F') ('_'? ('0'..'9'|'a'..'f'|'A'..'F'))*;

fragment RULE_VLOGINT : ('0'..'9')+ '\'' ('b' ('0'..'1')+|'o' ('0'..'7')+|'d' ('0'..'9')+|'h' ('0'..'9'|'a'..'f'|'A'..'F')+);

RULE_CHARCONST : ('u'|'U'|'L')? '\'' ('\\' .|~(('\\'|'\'')))* '\'';

RULE_INT : '~this one has been deactivated';

RULE_ID : '^'? ('a'..'z'|'A'..'Z'|'_') ('a'..'z'|'A'..'Z'|'_'|'0'..'9')*;

RULE_ENCSTRINGCONST : ('u8'|'u'|'U'|'L') '"' ('\\' .|~(('\\'|'"')))* '"';

RULE_STRING : ('"' ('\\' .|~(('\\'|'"')))* '"'|'\'' ('\\' .|~(('\\'|'\'')))* '\'');

RULE_ML_COMMENT : '/*' ( options {greedy=false;} : . )*'*/' {skip();};

RULE_SL_COMMENT : '//' ~(('\n'|'\r'))* ('\r'? '\n')? {skip();};

RULE_WS : (' '|'\t'|'\r'|'\n')+ {skip();};

RULE_ANY_OTHER : .;
