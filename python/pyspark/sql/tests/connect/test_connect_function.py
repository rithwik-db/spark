#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import unittest
import tempfile

from pyspark.sql import SparkSession
from pyspark.testing.pandasutils import PandasOnSparkTestCase
from pyspark.testing.connectutils import should_test_connect, connect_requirement_message
from pyspark.testing.utils import ReusedPySparkTestCase
from pyspark.testing.sqlutils import SQLTestUtils

if should_test_connect:
    import grpc
    from pyspark.sql.connect.session import SparkSession as RemoteSparkSession


@unittest.skipIf(not should_test_connect, connect_requirement_message)
class SparkConnectFuncTestCase(PandasOnSparkTestCase, ReusedPySparkTestCase, SQLTestUtils):
    """Parent test fixture class for all Spark Connect related
    test cases."""

    @classmethod
    def setUpClass(cls):
        ReusedPySparkTestCase.setUpClass()
        cls.tempdir = tempfile.NamedTemporaryFile(delete=False)
        cls.hive_available = True
        # Create the new Spark Session
        cls.spark = SparkSession(cls.sc)
        # Setup Remote Spark Session
        cls.connect = RemoteSparkSession.builder.remote().getOrCreate()

    @classmethod
    def tearDownClass(cls):
        ReusedPySparkTestCase.tearDownClass()


class SparkConnectFunctionTests(SparkConnectFuncTestCase):
    """These test cases exercise the interface to the proto plan
    generation but do not call Spark."""

    def compare_by_show(self, df1, df2, n: int = 20, truncate: int = 20):
        from pyspark.sql.dataframe import DataFrame as SDF
        from pyspark.sql.connect.dataframe import DataFrame as CDF

        assert isinstance(df1, (SDF, CDF))
        if isinstance(df1, SDF):
            str1 = df1._jdf.showString(n, truncate, False)
        else:
            str1 = df1._show_string(n, truncate, False)

        assert isinstance(df2, (SDF, CDF))
        if isinstance(df2, SDF):
            str2 = df2._jdf.showString(n, truncate, False)
        else:
            str2 = df2._show_string(n, truncate, False)

        self.assertEqual(str1, str2)

    def test_broadcast(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (0, float("NAN"), NULL), (1, NULL, 2.0), (2, 2.1, 3.5)
            AS tab(a, b, c)
            """
        # +---+----+----+
        # |  a|   b|   c|
        # +---+----+----+
        # |  0| NaN|null|
        # |  1|null| 2.0|
        # |  2| 2.1| 3.5|
        # +---+----+----+

        cdf = self.connect.sql(query)
        cdf1 = cdf.select(cdf.a, "b")
        cdf2 = cdf.select(cdf.a, "c")

        sdf = self.spark.sql(query)
        sdf1 = sdf.select(sdf.a, "b")
        sdf2 = sdf.select(sdf.a, "c")

        self.assert_eq(
            cdf1.join(cdf2, on="a").toPandas(),
            sdf1.join(sdf2, on="a").toPandas(),
        )
        self.assert_eq(
            cdf1.join(CF.broadcast(cdf2), on="a").toPandas(),
            sdf1.join(SF.broadcast(sdf2), on="a").toPandas(),
        )
        self.assert_eq(
            CF.broadcast(cdf1).join(cdf2, on="a").toPandas(),
            SF.broadcast(sdf1).join(sdf2, on="a").toPandas(),
        )
        self.assert_eq(
            CF.broadcast(cdf1).join(CF.broadcast(cdf2), on="a").toPandas(),
            SF.broadcast(sdf1).join(SF.broadcast(sdf2), on="a").toPandas(),
        )

    def test_normal_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (0, float("NAN"), NULL), (1, NULL, 2.0), (2, 2.1, 3.5)
            AS tab(a, b, c)
            """
        # +---+----+----+
        # |  a|   b|   c|
        # +---+----+----+
        # |  0| NaN|null|
        # |  1|null| 2.0|
        # |  2| 2.1| 3.5|
        # +---+----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        self.assert_eq(
            cdf.select(CF.bitwise_not(cdf.a)).toPandas(),
            sdf.select(SF.bitwise_not(sdf.a)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.bitwiseNOT(cdf.a)).toPandas(),
            sdf.select(SF.bitwiseNOT(sdf.a)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.coalesce(cdf.a, "b", cdf.c)).toPandas(),
            sdf.select(SF.coalesce(sdf.a, "b", sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.expr("a + b - c")).toPandas(),
            sdf.select(SF.expr("a + b - c")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.greatest(cdf.a, "b", cdf.c)).toPandas(),
            sdf.select(SF.greatest(sdf.a, "b", sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.isnan(cdf.a), CF.isnan("b")).toPandas(),
            sdf.select(SF.isnan(sdf.a), SF.isnan("b")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.isnull(cdf.a), CF.isnull("b")).toPandas(),
            sdf.select(SF.isnull(sdf.a), SF.isnull("b")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.input_file_name()).toPandas(),
            sdf.select(SF.input_file_name()).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.least(cdf.a, "b", cdf.c)).toPandas(),
            sdf.select(SF.least(sdf.a, "b", sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.monotonically_increasing_id()).toPandas(),
            sdf.select(SF.monotonically_increasing_id()).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.nanvl("b", cdf.c)).toPandas(),
            sdf.select(SF.nanvl("b", sdf.c)).toPandas(),
        )
        # Can not compare the values due to the random seed
        self.assertEqual(
            cdf.select(CF.rand()).count(),
            sdf.select(SF.rand()).count(),
        )
        self.assert_eq(
            cdf.select(CF.rand(100)).toPandas(),
            sdf.select(SF.rand(100)).toPandas(),
        )
        # Can not compare the values due to the random seed
        self.assertEqual(
            cdf.select(CF.randn()).count(),
            sdf.select(SF.randn()).count(),
        )
        self.assert_eq(
            cdf.select(CF.randn(100)).toPandas(),
            sdf.select(SF.randn(100)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.spark_partition_id()).toPandas(),
            sdf.select(SF.spark_partition_id()).toPandas(),
        )

    def test_when_otherwise(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (0, float("NAN"), NULL), (1, NULL, 2.0), (2, 2.1, 3.5), (3, 3.1, float("NAN"))
            AS tab(a, b, c)
            """
        # +---+----+----+
        # |  a|   b|   c|
        # +---+----+----+
        # |  0| NaN|null|
        # |  1|null| 2.0|
        # |  2| 2.1| 3.5|
        # |  3| 3.1| NaN|
        # +---+----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        self.assert_eq(
            cdf.select(CF.when(cdf.a == 0, 1.0).otherwise(2.0)).toPandas(),
            sdf.select(SF.when(sdf.a == 0, 1.0).otherwise(2.0)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.when(cdf.a < 1, cdf.b).otherwise(cdf.c)).toPandas(),
            sdf.select(SF.when(sdf.a < 1, sdf.b).otherwise(sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(
                CF.when(cdf.a == 0, 1.0)
                .when(CF.col("a") == 1, 2.0)
                .when(cdf.a == 2, -1.0)
                .otherwise(cdf.c)
            ).toPandas(),
            sdf.select(
                SF.when(sdf.a == 0, 1.0)
                .when(SF.col("a") == 1, 2.0)
                .when(sdf.a == 2, -1.0)
                .otherwise(sdf.c)
            ).toPandas(),
        )
        self.assert_eq(
            cdf.select(
                CF.when(cdf.a < cdf.b, 1.0)
                .when(CF.col("a") == 1, CF.abs("c") + cdf.b)
                .otherwise(cdf.c + CF.col("a"))
            ).toPandas(),
            sdf.select(
                SF.when(sdf.a < sdf.b, 1.0)
                .when(SF.col("a") == 1, SF.abs("c") + sdf.b)
                .otherwise(sdf.c + SF.col("a"))
            ).toPandas(),
        )

        # when without otherwise
        self.assert_eq(
            cdf.select(CF.when(cdf.a < 1, cdf.b)).toPandas(),
            sdf.select(SF.when(sdf.a < 1, sdf.b)).toPandas(),
        )
        self.assert_eq(
            cdf.select(
                CF.when(cdf.a == 0, 1.0)
                .when(CF.col("a") == 1, cdf.b + CF.col("c"))
                .when(cdf.a == 2, CF.abs(cdf.b))
            ).toPandas(),
            sdf.select(
                SF.when(sdf.a == 0, 1.0)
                .when(SF.col("a") == 1, sdf.b + SF.col("c"))
                .when(sdf.a == 2, SF.abs(sdf.b))
            ).toPandas(),
        )

        # check error
        with self.assertRaisesRegex(
            TypeError,
            "when.* can only be applied on a Column previously generated by when.* function",
        ):
            cdf.a.when(cdf.a == 0, 1.0)

        with self.assertRaisesRegex(
            TypeError,
            "when.* can only be applied on a Column previously generated by when.* function",
        ):
            CF.col("c").when(cdf.a == 0, 1.0)

        with self.assertRaisesRegex(
            TypeError,
            "otherwise.* can only be applied on a Column previously generated by when",
        ):
            cdf.a.otherwise(1.0)

        with self.assertRaisesRegex(
            TypeError,
            "otherwise.* can only be applied on a Column previously generated by when",
        ):
            CF.col("c").otherwise(1.0)

        with self.assertRaisesRegex(
            TypeError,
            "otherwise.* can only be applied once on a Column previously generated by when",
        ):
            CF.when(cdf.a == 0, 1.0).otherwise(1.0).otherwise(1.0)

        with self.assertRaisesRegex(
            TypeError,
            """condition should be a Column""",
        ):
            CF.when(True, 1.0).otherwise(1.0)

    def test_sorting_functions_with_column(self):
        from pyspark.sql.connect import functions as CF
        from pyspark.sql.connect.column import Column

        funs = [
            CF.asc_nulls_first,
            CF.asc_nulls_last,
            CF.desc_nulls_first,
            CF.desc_nulls_last,
        ]
        exprs = [CF.col("x"), "x"]

        for fun in funs:
            for _expr in exprs:
                res = fun(_expr)
                self.assertIsInstance(res, Column)
                self.assertIn(f"""{fun.__name__.replace("_", " ").upper()}'""", str(res))

        for _expr in exprs:
            res = CF.asc(_expr)
            self.assertIsInstance(res, Column)
            self.assertIn("""ASC NULLS FIRST'""", str(res))

        for _expr in exprs:
            res = CF.desc(_expr)
            self.assertIsInstance(res, Column)
            self.assertIn("""DESC NULLS LAST'""", str(res))

    def test_sort_with_nulls_order(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (false, 1, NULL), (true, NULL, 2.0), (NULL, 3, 3.0)
            AS tab(a, b, c)
            """
        # +-----+----+----+
        # |    a|   b|   c|
        # +-----+----+----+
        # |false|   1|null|
        # | true|null| 2.0|
        # | null|   3| 3.0|
        # +-----+----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        for c in ["a", "b", "c"]:
            self.assert_eq(
                cdf.orderBy(CF.asc(c)).toPandas(),
                sdf.orderBy(SF.asc(c)).toPandas(),
            )
            self.assert_eq(
                cdf.orderBy(CF.asc_nulls_first(c)).toPandas(),
                sdf.orderBy(SF.asc_nulls_first(c)).toPandas(),
            )
            self.assert_eq(
                cdf.orderBy(CF.asc_nulls_last(c)).toPandas(),
                sdf.orderBy(SF.asc_nulls_last(c)).toPandas(),
            )
            self.assert_eq(
                cdf.orderBy(CF.desc(c)).toPandas(),
                sdf.orderBy(SF.desc(c)).toPandas(),
            )
            self.assert_eq(
                cdf.orderBy(CF.desc_nulls_first(c)).toPandas(),
                sdf.orderBy(SF.desc_nulls_first(c)).toPandas(),
            )
            self.assert_eq(
                cdf.orderBy(CF.desc_nulls_last(c)).toPandas(),
                sdf.orderBy(SF.desc_nulls_last(c)).toPandas(),
            )

    def test_math_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (false, 1, NULL), (true, NULL, 2.0), (NULL, 3, 3.5)
            AS tab(a, b, c)
            """
        # +-----+----+----+
        # |    a|   b|   c|
        # +-----+----+----+
        # |false|   1|null|
        # | true|null| 2.0|
        # | null|   3| 3.5|
        # +-----+----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        for cfunc, sfunc in [
            (CF.abs, SF.abs),
            (CF.acos, SF.acos),
            (CF.acosh, SF.acosh),
            (CF.asin, SF.asin),
            (CF.asinh, SF.asinh),
            (CF.atan, SF.atan),
            (CF.atanh, SF.atanh),
            (CF.bin, SF.bin),
            (CF.cbrt, SF.cbrt),
            (CF.ceil, SF.ceil),
            (CF.cos, SF.cos),
            (CF.cosh, SF.cosh),
            (CF.cot, SF.cot),
            (CF.csc, SF.csc),
            (CF.degrees, SF.degrees),
            (CF.toDegrees, SF.toDegrees),
            (CF.exp, SF.exp),
            (CF.expm1, SF.expm1),
            (CF.factorial, SF.factorial),
            (CF.floor, SF.floor),
            (CF.hex, SF.hex),
            (CF.log, SF.log),
            (CF.log10, SF.log10),
            (CF.log1p, SF.log1p),
            (CF.log2, SF.log2),
            (CF.radians, SF.radians),
            (CF.toRadians, SF.toRadians),
            (CF.rint, SF.rint),
            (CF.sec, SF.sec),
            (CF.signum, SF.signum),
            (CF.sin, SF.sin),
            (CF.sinh, SF.sinh),
            (CF.sqrt, SF.sqrt),
            (CF.tan, SF.tan),
            (CF.tanh, SF.tanh),
            (CF.unhex, SF.unhex),
        ]:
            self.assert_eq(
                cdf.select(cfunc("b"), cfunc(cdf.c)).toPandas(),
                sdf.select(sfunc("b"), sfunc(sdf.c)).toPandas(),
            )

        self.assert_eq(
            cdf.select(CF.atan2("b", cdf.c)).toPandas(),
            sdf.select(SF.atan2("b", sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.bround("b", 1)).toPandas(),
            sdf.select(SF.bround("b", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.conv("b", 2, 16)).toPandas(),
            sdf.select(SF.conv("b", 2, 16)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.hypot("b", cdf.c)).toPandas(),
            sdf.select(SF.hypot("b", sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.pmod("b", cdf.c)).toPandas(),
            sdf.select(SF.pmod("b", sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.pow("b", cdf.c)).toPandas(),
            sdf.select(SF.pow("b", sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.round("b", 1)).toPandas(),
            sdf.select(SF.round("b", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.shiftleft("b", 1)).toPandas(),
            sdf.select(SF.shiftleft("b", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.shiftLeft("b", 1)).toPandas(),
            sdf.select(SF.shiftLeft("b", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.shiftright("b", 1)).toPandas(),
            sdf.select(SF.shiftright("b", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.shiftRight("b", 1)).toPandas(),
            sdf.select(SF.shiftRight("b", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.shiftrightunsigned("b", 1)).toPandas(),
            sdf.select(SF.shiftrightunsigned("b", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.shiftRightUnsigned("b", 1)).toPandas(),
            sdf.select(SF.shiftRightUnsigned("b", 1)).toPandas(),
        )

    def test_aggregation_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (0, float("NAN"), NULL), (1, NULL, 2.0), (1, 2.1, 3.5), (0, 0.5, 1.0)
            AS tab(a, b, c)
            """
        # +---+----+----+
        # |  a|   b|   c|
        # +---+----+----+
        # |  0| NaN|null|
        # |  1|null| 2.0|
        # |  1| 2.1| 3.5|
        # |  0| 0.5| 1.0|
        # +---+----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # TODO(SPARK-41383): add tests for grouping, grouping_id after DataFrame.cube is supported.
        for cfunc, sfunc in [
            (CF.approx_count_distinct, SF.approx_count_distinct),
            (CF.approxCountDistinct, SF.approxCountDistinct),
            (CF.avg, SF.avg),
            (CF.collect_list, SF.collect_list),
            (CF.collect_set, SF.collect_set),
            (CF.count, SF.count),
            (CF.first, SF.first),
            (CF.kurtosis, SF.kurtosis),
            (CF.last, SF.last),
            (CF.max, SF.max),
            (CF.mean, SF.mean),
            (CF.median, SF.median),
            (CF.min, SF.min),
            (CF.mode, SF.mode),
            (CF.product, SF.product),
            (CF.skewness, SF.skewness),
            (CF.stddev, SF.stddev),
            (CF.stddev_pop, SF.stddev_pop),
            (CF.stddev_samp, SF.stddev_samp),
            (CF.sum, SF.sum),
            (CF.sum_distinct, SF.sum_distinct),
            (CF.sumDistinct, SF.sumDistinct),
            (CF.var_pop, SF.var_pop),
            (CF.var_samp, SF.var_samp),
            (CF.variance, SF.variance),
        ]:
            self.assert_eq(
                cdf.select(cfunc("b"), cfunc(cdf.c)).toPandas(),
                sdf.select(sfunc("b"), sfunc(sdf.c)).toPandas(),
            )
            self.assert_eq(
                cdf.groupBy("a").agg(cfunc("b"), cfunc(cdf.c)).toPandas(),
                sdf.groupBy("a").agg(sfunc("b"), sfunc(sdf.c)).toPandas(),
            )

        for cfunc, sfunc in [
            (CF.corr, SF.corr),
            (CF.covar_pop, SF.covar_pop),
            (CF.covar_samp, SF.covar_samp),
            (CF.max_by, SF.max_by),
            (CF.min_by, SF.min_by),
        ]:
            self.assert_eq(
                cdf.select(cfunc(cdf.b, "c")).toPandas(),
                sdf.select(sfunc(sdf.b, "c")).toPandas(),
            )
            self.assert_eq(
                cdf.groupBy("a").agg(cfunc(cdf.b, "c")).toPandas(),
                sdf.groupBy("a").agg(sfunc(sdf.b, "c")).toPandas(),
            )

        # test percentile_approx
        self.assert_eq(
            cdf.select(CF.percentile_approx(cdf.b, 0.5, 1000)).toPandas(),
            sdf.select(SF.percentile_approx(sdf.b, 0.5, 1000)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.percentile_approx(cdf.b, [0.1, 0.9])).toPandas(),
            sdf.select(SF.percentile_approx(sdf.b, [0.1, 0.9])).toPandas(),
        )
        self.assert_eq(
            cdf.groupBy("a").agg(CF.percentile_approx("b", 0.5)).toPandas(),
            sdf.groupBy("a").agg(SF.percentile_approx("b", 0.5)).toPandas(),
        )
        self.assert_eq(
            cdf.groupBy("a").agg(CF.percentile_approx(cdf.b, [0.1, 0.9])).toPandas(),
            sdf.groupBy("a").agg(SF.percentile_approx(sdf.b, [0.1, 0.9])).toPandas(),
        )

        # test count_distinct
        self.assert_eq(
            cdf.select(CF.count_distinct("b"), CF.count_distinct(cdf.c)).toPandas(),
            sdf.select(SF.count_distinct("b"), SF.count_distinct(sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.countDistinct("b"), CF.countDistinct(cdf.c)).toPandas(),
            sdf.select(SF.countDistinct("b"), SF.countDistinct(sdf.c)).toPandas(),
        )
        # The output column names of 'groupBy.agg(count_distinct)' in PySpark
        # are incorrect, see SPARK-41391.
        self.assert_eq(
            cdf.groupBy("a")
            .agg(CF.count_distinct("b").alias("x"), CF.count_distinct(cdf.c).alias("y"))
            .toPandas(),
            sdf.groupBy("a")
            .agg(SF.count_distinct("b").alias("x"), SF.count_distinct(sdf.c).alias("y"))
            .toPandas(),
        )

    def test_window_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.window import Window as SW
        from pyspark.sql.connect import functions as CF
        from pyspark.sql.connect.window import Window as CW

        self.assertEqual(CW.unboundedPreceding, SW.unboundedPreceding)

        self.assertEqual(CW.unboundedFollowing, SW.unboundedFollowing)

        self.assertEqual(CW.currentRow, SW.currentRow)

        query = """
            SELECT * FROM VALUES
            (0, float("NAN"), NULL), (1, NULL, 2.0), (1, 2.1, 3.5), (0, 0.5, 1.0),
            (0, 1.5, 1.1), (1, 2.2, -1.0), (1, 0.1, -0.1), (0, 0.0, 5.0)
            AS tab(a, b, c)
            """
        # +---+----+----+
        # |  a|   b|   c|
        # +---+----+----+
        # |  0| NaN|null|
        # |  1|null| 2.0|
        # |  1| 2.1| 3.5|
        # |  0| 0.5| 1.0|
        # |  0| 1.5| 1.1|
        # |  1| 2.2|-1.0|
        # |  1| 0.1|-0.1|
        # |  0| 0.0| 5.0|
        # +---+----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # test window functions
        for ccol, scol in [
            (CF.row_number(), SF.row_number()),
            (CF.rank(), SF.rank()),
            (CF.dense_rank(), SF.dense_rank()),
            (CF.percent_rank(), SF.percent_rank()),
            (CF.cume_dist(), SF.cume_dist()),
            (CF.lag("c", 1), SF.lag("c", 1)),
            (CF.lag("c", 1, -1.0), SF.lag("c", 1, -1.0)),
            (CF.lag(cdf.c, -1), SF.lag(sdf.c, -1)),
            (CF.lag(cdf.c, -1, float("nan")), SF.lag(sdf.c, -1, float("nan"))),
            (CF.lead("c", 1), SF.lead("c", 1)),
            (CF.lead("c", 1, -1.0), SF.lead("c", 1, -1.0)),
            (CF.lead(cdf.c, -1), SF.lead(sdf.c, -1)),
            (CF.lead(cdf.c, -1, float("nan")), SF.lead(sdf.c, -1, float("nan"))),
            (CF.nth_value("c", 1), SF.nth_value("c", 1)),
            (CF.nth_value(cdf.c, 2), SF.nth_value(sdf.c, 2)),
            (CF.nth_value(cdf.c, 2, True), SF.nth_value(sdf.c, 2, True)),
            (CF.nth_value(cdf.c, 2, False), SF.nth_value(sdf.c, 2, False)),
            (CF.ntile(1), SF.ntile(1)),
            (CF.ntile(2), SF.ntile(2)),
            (CF.ntile(4), SF.ntile(4)),
        ]:

            for cwin, swin in [
                (CW.orderBy("b"), SW.orderBy("b")),
                (CW.partitionBy("a").orderBy("b"), SW.partitionBy("a").orderBy("b")),
                (
                    CW.partitionBy("a").orderBy(CF.col("b").desc()),
                    SW.partitionBy("a").orderBy(SF.col("b").desc()),
                ),
                (CW.partitionBy("a", cdf.c).orderBy("b"), SW.partitionBy("a", sdf.c).orderBy("b")),
                (CW.partitionBy("a").orderBy("b", cdf.c), SW.partitionBy("a").orderBy("b", sdf.c)),
                (
                    CW.partitionBy("a").orderBy("b", cdf.c.desc()),
                    SW.partitionBy("a").orderBy("b", sdf.c.desc()),
                ),
            ]:

                self.assert_eq(
                    cdf.select(ccol.over(cwin)).toPandas(),
                    sdf.select(scol.over(swin)).toPandas(),
                )

        # test aggregation functions
        for ccol, scol in [
            (CF.count("c"), SF.count("c")),
            (CF.sum("c"), SF.sum("c")),
            (CF.max(cdf.c), SF.max(sdf.c)),
            (CF.min(cdf.c), SF.min(sdf.c)),
        ]:

            for cwin, swin in [
                (CW.orderBy("b"), SW.orderBy("b")),
                (
                    CW.orderBy("b").rowsBetween(CW.currentRow, CW.currentRow),
                    SW.orderBy("b").rowsBetween(SW.currentRow, SW.currentRow),
                ),
                (
                    CW.orderBy(cdf.b.desc()).rowsBetween(CW.currentRow - 1, CW.currentRow + 2),
                    SW.orderBy(sdf.b.desc()).rowsBetween(SW.currentRow - 1, SW.currentRow + 2),
                ),
                (
                    CW.orderBy("b").rowsBetween(CW.unboundedPreceding, CW.currentRow),
                    SW.orderBy("b").rowsBetween(SW.unboundedPreceding, SW.currentRow),
                ),
                (
                    CW.orderBy(cdf.b.desc()).rowsBetween(CW.currentRow, CW.unboundedFollowing),
                    SW.orderBy(sdf.b.desc()).rowsBetween(SW.currentRow, SW.unboundedFollowing),
                ),
                (
                    CW.orderBy("b").rangeBetween(CW.currentRow, CW.currentRow),
                    SW.orderBy("b").rangeBetween(SW.currentRow, SW.currentRow),
                ),
                (
                    CW.orderBy("b").rangeBetween(CW.currentRow - 1, CW.currentRow + 2),
                    SW.orderBy("b").rangeBetween(SW.currentRow - 1, SW.currentRow + 2),
                ),
                (
                    CW.orderBy("b").rangeBetween(CW.unboundedPreceding, CW.currentRow),
                    SW.orderBy("b").rangeBetween(SW.unboundedPreceding, SW.currentRow),
                ),
                (
                    CW.orderBy("b").rangeBetween(CW.currentRow, CW.unboundedFollowing),
                    SW.orderBy("b").rangeBetween(SW.currentRow, SW.unboundedFollowing),
                ),
                (CW.partitionBy("a").orderBy("b"), SW.partitionBy("a").orderBy("b")),
                (
                    CW.partitionBy(cdf.a)
                    .orderBy(CF.asc_nulls_last("b"))
                    .rowsBetween(CW.currentRow, CW.currentRow),
                    SW.partitionBy(sdf.a)
                    .orderBy(SF.asc_nulls_last("b"))
                    .rowsBetween(SW.currentRow, SW.currentRow),
                ),
                (
                    CW.partitionBy("a")
                    .orderBy(cdf.b.desc())
                    .rowsBetween(CW.currentRow - 1, CW.currentRow + 2),
                    SW.partitionBy("a")
                    .orderBy(sdf.b.desc())
                    .rowsBetween(SW.currentRow - 1, SW.currentRow + 2),
                ),
                (
                    CW.partitionBy("a")
                    .orderBy("b")
                    .rowsBetween(CW.unboundedPreceding, CW.currentRow),
                    SW.partitionBy("a")
                    .orderBy("b")
                    .rowsBetween(SW.unboundedPreceding, SW.currentRow),
                ),
                (
                    CW.partitionBy("a")
                    .orderBy("b")
                    .rowsBetween(CW.currentRow, CW.unboundedFollowing),
                    SW.partitionBy("a")
                    .orderBy("b")
                    .rowsBetween(SW.currentRow, SW.unboundedFollowing),
                ),
                (
                    CW.partitionBy(cdf.a)
                    .orderBy(cdf.b.desc(), "c")
                    .rangeBetween(CW.currentRow, CW.currentRow),
                    SW.partitionBy(sdf.a)
                    .orderBy(sdf.b.desc(), "c")
                    .rangeBetween(SW.currentRow, SW.currentRow),
                ),
                (
                    CW.partitionBy("a")
                    .orderBy("b")
                    .rangeBetween(CW.currentRow - 1, CW.currentRow + 2),
                    SW.partitionBy("a")
                    .orderBy("b")
                    .rangeBetween(SW.currentRow - 1, SW.currentRow + 2),
                ),
                (
                    CW.partitionBy("a")
                    .orderBy(CF.desc_nulls_last("b"))
                    .rangeBetween(CW.unboundedPreceding, CW.currentRow),
                    SW.partitionBy("a")
                    .orderBy(SF.desc_nulls_last("b"))
                    .rangeBetween(SW.unboundedPreceding, SW.currentRow),
                ),
                (
                    CW.partitionBy("a")
                    .orderBy("b")
                    .rangeBetween(CW.currentRow, CW.unboundedFollowing),
                    SW.partitionBy("a")
                    .orderBy("b")
                    .rangeBetween(SW.currentRow, SW.unboundedFollowing),
                ),
            ]:

                self.assert_eq(
                    cdf.select(ccol.over(cwin)).toPandas(),
                    sdf.select(scol.over(swin)).toPandas(),
                )

        # check error
        with self.assertRaisesRegex(
            ValueError,
            "end is out of bound",
        ):
            cdf.select(CF.sum("a").over(CW.orderBy("b").rowsBetween(0, (1 << 33)))).show()

        with self.assertRaisesRegex(
            TypeError,
            "window should be WindowSpec",
        ):
            cdf.select(CF.rank().over(cdf.a))

        # invalid window function
        with self.assertRaises(grpc.RpcError):
            cdf.select(cdf.b.over(CW.orderBy("b"))).show()

        # invalid window frame
        # following functions require Windowframe(RowFrame, UnboundedPreceding, CurrentRow)
        for ccol in [
            CF.row_number(),
            CF.rank(),
            CF.dense_rank(),
            CF.percent_rank(),
            CF.lag("c", 1),
            CF.lead("c", 1),
            CF.ntile(1),
        ]:
            with self.assertRaises(grpc.RpcError):
                cdf.select(
                    ccol.over(CW.orderBy("b").rowsBetween(CW.currentRow, CW.currentRow + 123))
                ).show()

            with self.assertRaises(grpc.RpcError):
                cdf.select(
                    ccol.over(CW.orderBy("b").rangeBetween(CW.currentRow, CW.currentRow + 123))
                ).show()

            with self.assertRaises(grpc.RpcError):
                cdf.select(
                    ccol.over(CW.orderBy("b").rangeBetween(CW.unboundedPreceding, CW.currentRow))
                ).show()

        # Function 'cume_dist' requires Windowframe(RangeFrame, UnboundedPreceding, CurrentRow)
        ccol = CF.cume_dist()
        with self.assertRaises(grpc.RpcError):
            cdf.select(
                ccol.over(CW.orderBy("b").rangeBetween(CW.currentRow, CW.currentRow + 123))
            ).show()

        with self.assertRaises(grpc.RpcError):
            cdf.select(
                ccol.over(CW.orderBy("b").rowsBetween(CW.currentRow, CW.currentRow + 123))
            ).show()

        with self.assertRaises(grpc.RpcError):
            cdf.select(
                ccol.over(CW.orderBy("b").rowsBetween(CW.unboundedPreceding, CW.currentRow))
            ).show()

    def test_collection_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (ARRAY('a', 'ab'), ARRAY(1, 2, 3), ARRAY(1, NULL, 3), 1, 2, 'a'),
            (ARRAY('x', NULL), NULL, ARRAY(1, 3), 3, 4, 'x'),
            (NULL, ARRAY(-1, -2, -3), Array(), 5, 6, NULL)
            AS tab(a, b, c, d, e, f)
            """
        # +---------+------------+------------+---+---+----+
        # |        a|           b|           c|  d|  e|   f|
        # +---------+------------+------------+---+---+----+
        # |  [a, ab]|   [1, 2, 3]|[1, null, 3]|  1|  2|   a|
        # |[x, null]|        null|      [1, 3]|  3|  4|   x|
        # |     null|[-1, -2, -3]|          []|  5|  6|null|
        # +---------+------------+------------+---+---+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        for cfunc, sfunc in [
            (CF.array_distinct, SF.array_distinct),
            (CF.array_max, SF.array_max),
            (CF.array_min, SF.array_min),
            (CF.reverse, SF.reverse),
            (CF.size, SF.size),
        ]:
            self.assert_eq(
                cdf.select(cfunc("a"), cfunc(cdf.b)).toPandas(),
                sdf.select(sfunc("a"), sfunc(sdf.b)).toPandas(),
            )

        for cfunc, sfunc in [
            (CF.array_except, SF.array_except),
            (CF.array_intersect, SF.array_intersect),
            (CF.array_union, SF.array_union),
            (CF.arrays_overlap, SF.arrays_overlap),
        ]:
            self.assert_eq(
                cdf.select(cfunc("b", cdf.c)).toPandas(),
                sdf.select(sfunc("b", sdf.c)).toPandas(),
            )

        for cfunc, sfunc in [
            (CF.array_position, SF.array_position),
            (CF.array_remove, SF.array_remove),
        ]:
            self.assert_eq(
                cdf.select(cfunc(cdf.a, "ab")).toPandas(),
                sdf.select(sfunc(sdf.a, "ab")).toPandas(),
            )

        # test array
        self.assert_eq(
            cdf.select(CF.array(cdf.d, "e")).toPandas(),
            sdf.select(SF.array(sdf.d, "e")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.array(cdf.d, "e", CF.lit(99))).toPandas(),
            sdf.select(SF.array(sdf.d, "e", SF.lit(99))).toPandas(),
        )

        # test array_contains
        self.assert_eq(
            cdf.select(CF.array_contains(cdf.a, "ab")).toPandas(),
            sdf.select(SF.array_contains(sdf.a, "ab")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.array_contains(cdf.a, cdf.f)).toPandas(),
            sdf.select(SF.array_contains(sdf.a, sdf.f)).toPandas(),
        )

        # test array_join
        self.assert_eq(
            cdf.select(
                CF.array_join(cdf.a, ","), CF.array_join("b", ":"), CF.array_join("c", "~")
            ).toPandas(),
            sdf.select(
                SF.array_join(sdf.a, ","), SF.array_join("b", ":"), SF.array_join("c", "~")
            ).toPandas(),
        )
        self.assert_eq(
            cdf.select(
                CF.array_join(cdf.a, ",", "_null_"),
                CF.array_join("b", ":", ".null."),
                CF.array_join("c", "~", "NULL"),
            ).toPandas(),
            sdf.select(
                SF.array_join(sdf.a, ",", "_null_"),
                SF.array_join("b", ":", ".null."),
                SF.array_join("c", "~", "NULL"),
            ).toPandas(),
        )

        # test array_repeat
        self.assert_eq(
            cdf.select(CF.array_repeat(cdf.f, "d")).toPandas(),
            sdf.select(SF.array_repeat(sdf.f, "d")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.array_repeat("f", cdf.d)).toPandas(),
            sdf.select(SF.array_repeat("f", sdf.d)).toPandas(),
        )
        # TODO: Make Literal contains DataType
        #   Cannot resolve "array_repeat(f, 3)" due to data type mismatch:
        #   Parameter 2 requires the "INT" type, however "3" has the type "BIGINT".
        # self.assert_eq(
        #     cdf.select(CF.array_repeat("f", 3)).toPandas(),
        #     sdf.select(SF.array_repeat("f", 3)).toPandas(),
        # )

        # test arrays_zip
        # TODO: Make toPandas support complex nested types like Array<Struct>
        # DataFrame.iloc[:, 0] (column name="arrays_zip(b, c)") values are different (66.66667 %)
        # [index]: [0, 1, 2]
        # [left]:  [[{'b': 1, 'c': 1.0}, {'b': 2, 'c': None}, {'b': 3, 'c': 3.0}], None,
        #           [{'b': -1, 'c': None}, {'b': -2, 'c': None}, {'b': -3, 'c': None}]]
        # [right]: [[(1, 1), (2, None), (3, 3)], None, [(-1, None), (-2, None), (-3, None)]]
        self.compare_by_show(
            cdf.select(CF.arrays_zip(cdf.b, "c")),
            sdf.select(SF.arrays_zip(sdf.b, "c")),
        )

        # test concat
        self.assert_eq(
            cdf.select(CF.concat("d", cdf.e, CF.lit(-1))).toPandas(),
            sdf.select(SF.concat("d", sdf.e, SF.lit(-1))).toPandas(),
        )

        # test create_map
        self.compare_by_show(
            cdf.select(CF.create_map(cdf.d, cdf.e)), sdf.select(SF.create_map(sdf.d, sdf.e))
        )
        self.compare_by_show(
            cdf.select(CF.create_map(cdf.d, "e", "e", CF.lit(1))),
            sdf.select(SF.create_map(sdf.d, "e", "e", SF.lit(1))),
        )

        # test element_at
        self.assert_eq(
            cdf.select(CF.element_at("a", 1)).toPandas(),
            sdf.select(SF.element_at("a", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.element_at(cdf.a, 1)).toPandas(),
            sdf.select(SF.element_at(sdf.a, 1)).toPandas(),
        )

        # test get
        self.assert_eq(
            cdf.select(CF.get("a", 1)).toPandas(),
            sdf.select(SF.get("a", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.get(cdf.a, 1)).toPandas(),
            sdf.select(SF.get(sdf.a, 1)).toPandas(),
        )

        # test shuffle
        # Can not compare the values due to the random permutation
        self.assertEqual(
            cdf.select(CF.shuffle(cdf.a), CF.shuffle("b")).count(),
            sdf.select(SF.shuffle(sdf.a), SF.shuffle("b")).count(),
        )

        # test slice
        self.assert_eq(
            cdf.select(CF.slice(cdf.a, 1, 2), CF.slice("c", 2, 3)).toPandas(),
            sdf.select(SF.slice(sdf.a, 1, 2), SF.slice("c", 2, 3)).toPandas(),
        )

        # test sort_array
        self.assert_eq(
            cdf.select(CF.sort_array(cdf.a, True), CF.sort_array("c", False)).toPandas(),
            sdf.select(SF.sort_array(sdf.a, True), SF.sort_array("c", False)).toPandas(),
        )

        # test struct
        self.compare_by_show(
            cdf.select(CF.struct(cdf.a, "d", "e", cdf.f)),
            sdf.select(SF.struct(sdf.a, "d", "e", sdf.f)),
        )

        # test sequence
        self.assert_eq(
            cdf.select(CF.sequence(CF.lit(1), CF.lit(5))).toPandas(),
            sdf.select(SF.sequence(SF.lit(1), SF.lit(5))).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.sequence(CF.lit(1), CF.lit(5), CF.lit(1))).toPandas(),
            sdf.select(SF.sequence(SF.lit(1), SF.lit(5), SF.lit(1))).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.sequence(cdf.d, "e")).toPandas(),
            sdf.select(SF.sequence(sdf.d, "e")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.sequence(cdf.d, "e", CF.lit(1))).toPandas(),
            sdf.select(SF.sequence(sdf.d, "e", SF.lit(1))).toPandas(),
        )

    def test_map_collection_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (MAP('a', 'ab'), MAP('x', 'ab'), MAP(1, 2, 3, 4), 1, 'a', ARRAY(1, 2), ARRAY('X', 'Y')),
            (MAP('x', 'yz'), MAP('c', NULL), NULL, 2, 'x', ARRAY(3, 4), ARRAY('A', 'B')),
            (MAP('c', 'de'), NULL, MAP(-1, NULL, -3, -4), -3, 'c', NULL, ARRAY('Z'))
            AS tab(a, b, c, e, f, g, h)
            """
        # +---------+-----------+----------------------+---+---+------+------+
        # |        a|          b|                     c|  e|  f|     g|     h|
        # +---------+-----------+----------------------+---+---+------+------+
        # |{a -> ab}|  {x -> ab}|      {1 -> 2, 3 -> 4}|  1|  a|[1, 2]|[X, Y]|
        # |{x -> yz}|{c -> null}|                  null|  2|  x|[3, 4]|[A, B]|
        # |{c -> de}|       null|{-1 -> null, -3 -> -4}| -3|  c|  null|   [Z]|
        # +---------+-----------+----------------------+---+---+------+------+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # test map_concat
        self.compare_by_show(
            cdf.select(CF.map_concat(cdf.a, "b")),
            sdf.select(SF.map_concat(sdf.a, "b")),
        )

        # test map_contains_key
        self.compare_by_show(
            cdf.select(CF.map_contains_key(cdf.a, "a"), CF.map_contains_key("c", 3)),
            sdf.select(SF.map_contains_key(sdf.a, "a"), SF.map_contains_key("c", 3)),
        )

        # test map_entries
        self.compare_by_show(
            cdf.select(CF.map_entries(cdf.a), CF.map_entries("b")),
            sdf.select(SF.map_entries(sdf.a), SF.map_entries("b")),
        )

        # test map_from_arrays
        self.compare_by_show(
            cdf.select(CF.map_from_arrays(cdf.g, "h")),
            sdf.select(SF.map_from_arrays(sdf.g, "h")),
        )

        # test map_keys and map_values
        self.compare_by_show(
            cdf.select(CF.map_keys(cdf.a), CF.map_values("b")),
            sdf.select(SF.map_keys(sdf.a), SF.map_values("b")),
        )

        # test size
        self.assert_eq(
            cdf.select(CF.size(cdf.a), CF.size("c")).toPandas(),
            sdf.select(SF.size(sdf.a), SF.size("c")).toPandas(),
        )

    def test_generator_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (ARRAY('a', 'ab'), ARRAY(1, 2, 3), ARRAY(1, NULL, 3),
             MAP(1, 2, 3, 4), 1, FLOAT(2.0), 3),
            (ARRAY('x', NULL), NULL, ARRAY(1, 3),
             NULL, 3, FLOAT(4.0), 5),
            (NULL, ARRAY(-1, -2, -3), Array(),
             MAP(-1, NULL, -3, -4), 7, FLOAT('NAN'), 9)
            AS tab(a, b, c, d, e, f, g)
            """
        # +---------+------------+------------+----------------------+---+---+---+
        # |        a|           b|           c|                     d|  e|  f|  g|
        # +---------+------------+------------+----------------------+---+---+---+
        # |  [a, ab]|   [1, 2, 3]|[1, null, 3]|      {1 -> 2, 3 -> 4}|  1|2.0|  3|
        # |[x, null]|        null|      [1, 3]|                  null|  3|4.0|  5|
        # |     null|[-1, -2, -3]|          []|{-1 -> null, -3 -> -4}|  7|NaN|  9|
        # +---------+------------+------------+----------------------+---+---+---+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # test explode with arrays
        self.assert_eq(
            cdf.select(CF.explode(cdf.a), CF.col("b")).toPandas(),
            sdf.select(SF.explode(sdf.a), SF.col("b")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.explode("a"), "b").toPandas(),
            sdf.select(SF.explode("a"), "b").toPandas(),
        )
        # test explode with maps
        self.assert_eq(
            cdf.select(CF.explode(cdf.d), CF.col("c")).toPandas(),
            sdf.select(SF.explode(sdf.d), SF.col("c")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.explode("d"), "c").toPandas(),
            sdf.select(SF.explode("d"), "c").toPandas(),
        )

        # test explode_outer with arrays
        self.assert_eq(
            cdf.select(CF.explode_outer(cdf.a), CF.col("b")).toPandas(),
            sdf.select(SF.explode_outer(sdf.a), SF.col("b")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.explode_outer("a"), "b").toPandas(),
            sdf.select(SF.explode_outer("a"), "b").toPandas(),
        )
        # test explode_outer with maps
        self.assert_eq(
            cdf.select(CF.explode_outer(cdf.d), CF.col("c")).toPandas(),
            sdf.select(SF.explode_outer(sdf.d), SF.col("c")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.explode_outer("d"), "c").toPandas(),
            sdf.select(SF.explode_outer("d"), "c").toPandas(),
        )

        # test flatten
        self.assert_eq(
            cdf.select(CF.flatten(CF.array("b", cdf.c)), CF.col("b")).toPandas(),
            sdf.select(SF.flatten(SF.array("b", sdf.c)), SF.col("b")).toPandas(),
        )

        # test inline
        self.assert_eq(
            cdf.select(CF.expr("ARRAY(STRUCT(e, f), STRUCT(g AS e, f))").alias("X"))
            .select(CF.inline("X"))
            .toPandas(),
            sdf.select(SF.expr("ARRAY(STRUCT(e, f), STRUCT(g AS e, f))").alias("X"))
            .select(SF.inline("X"))
            .toPandas(),
        )

        # test inline_outer
        self.assert_eq(
            cdf.select(CF.expr("ARRAY(STRUCT(e, f), STRUCT(g AS e, f))").alias("X"))
            .select(CF.inline_outer("X"))
            .toPandas(),
            sdf.select(SF.expr("ARRAY(STRUCT(e, f), STRUCT(g AS e, f))").alias("X"))
            .select(SF.inline_outer("X"))
            .toPandas(),
        )

        # test posexplode with arrays
        self.assert_eq(
            cdf.select(CF.posexplode(cdf.a), CF.col("b")).toPandas(),
            sdf.select(SF.posexplode(sdf.a), SF.col("b")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.posexplode("a"), "b").toPandas(),
            sdf.select(SF.posexplode("a"), "b").toPandas(),
        )
        # test posexplode with maps
        self.assert_eq(
            cdf.select(CF.posexplode(cdf.d), CF.col("c")).toPandas(),
            sdf.select(SF.posexplode(sdf.d), SF.col("c")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.posexplode("d"), "c").toPandas(),
            sdf.select(SF.posexplode("d"), "c").toPandas(),
        )

        # test posexplode_outer with arrays
        self.assert_eq(
            cdf.select(CF.posexplode_outer(cdf.a), CF.col("b")).toPandas(),
            sdf.select(SF.posexplode_outer(sdf.a), SF.col("b")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.posexplode_outer("a"), "b").toPandas(),
            sdf.select(SF.posexplode_outer("a"), "b").toPandas(),
        )
        # test posexplode_outer with maps
        self.assert_eq(
            cdf.select(CF.posexplode_outer(cdf.d), CF.col("c")).toPandas(),
            sdf.select(SF.posexplode_outer(sdf.d), SF.col("c")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.posexplode_outer("d"), "c").toPandas(),
            sdf.select(SF.posexplode_outer("d"), "c").toPandas(),
        )

    def test_lambda_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (ARRAY('a', 'ab'), ARRAY(1, 2, 3), ARRAY(1, NULL, 3), 1, 2, 'a', NULL, MAP(0, 0)),
            (ARRAY('x', NULL), NULL, ARRAY(1, 3), 3, 4, 'x', MAP(2, 0), MAP(-1, 1)),
            (NULL, ARRAY(-1, -2, -3), Array(), 5, 6, NULL, MAP(-1, 2, -3, -4), NULL)
            AS tab(a, b, c, d, e, f, g, h)
            """
        # +---------+------------+------------+---+---+----+-------------------+---------+
        # |        a|           b|           c|  d|  e|   f|                  g|        h|
        # +---------+------------+------------+---+---+----+-------------------+---------+
        # |  [a, ab]|   [1, 2, 3]|[1, null, 3]|  1|  2|   a|               null| {0 -> 0}|
        # |[x, null]|        null|      [1, 3]|  3|  4|   x|           {2 -> 0}|{-1 -> 1}|
        # |     null|[-1, -2, -3]|          []|  5|  6|null|{-1 -> 2, -3 -> -4}|     null|
        # +---------+------------+------------+---+---+----+-------------------+---------+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # test exists
        self.assert_eq(
            cdf.select(CF.exists(cdf.b, lambda x: x < 0)).toPandas(),
            sdf.select(SF.exists(sdf.b, lambda x: x < 0)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.exists("a", lambda x: CF.isnull(x))).toPandas(),
            sdf.select(SF.exists("a", lambda x: SF.isnull(x))).toPandas(),
        )

        # test aggregate
        # aggregate without finish
        self.assert_eq(
            cdf.select(CF.aggregate(cdf.b, "d", lambda acc, x: acc + x)).toPandas(),
            sdf.select(SF.aggregate(sdf.b, "d", lambda acc, x: acc + x)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.aggregate("b", cdf.d, lambda acc, x: acc + x)).toPandas(),
            sdf.select(SF.aggregate("b", sdf.d, lambda acc, x: acc + x)).toPandas(),
        )

        # aggregate with finish
        self.assert_eq(
            cdf.select(
                CF.aggregate(cdf.b, "d", lambda acc, x: acc + x, lambda acc: acc + 100)
            ).toPandas(),
            sdf.select(
                SF.aggregate(sdf.b, "d", lambda acc, x: acc + x, lambda acc: acc + 100)
            ).toPandas(),
        )
        self.assert_eq(
            cdf.select(
                CF.aggregate("b", cdf.d, lambda acc, x: acc + x, lambda acc: acc + 100)
            ).toPandas(),
            sdf.select(
                SF.aggregate("b", sdf.d, lambda acc, x: acc + x, lambda acc: acc + 100)
            ).toPandas(),
        )

        # test array_sort
        self.assert_eq(
            cdf.select(CF.array_sort(cdf.b, lambda x, y: CF.abs(x) - CF.abs(y))).toPandas(),
            sdf.select(SF.array_sort(sdf.b, lambda x, y: SF.abs(x) - SF.abs(y))).toPandas(),
        )
        self.assert_eq(
            cdf.select(
                CF.array_sort(
                    "a",
                    lambda x, y: CF.when(x.isNull() | y.isNull(), CF.lit(0)).otherwise(
                        CF.length(y) - CF.length(x)
                    ),
                )
            ).toPandas(),
            sdf.select(
                SF.array_sort(
                    "a",
                    lambda x, y: SF.when(x.isNull() | y.isNull(), SF.lit(0)).otherwise(
                        SF.length(y) - SF.length(x)
                    ),
                )
            ).toPandas(),
        )

        # test filter
        self.assert_eq(
            cdf.select(CF.filter(cdf.b, lambda x: x < 0)).toPandas(),
            sdf.select(SF.filter(sdf.b, lambda x: x < 0)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.filter("a", lambda x: ~CF.isnull(x))).toPandas(),
            sdf.select(SF.filter("a", lambda x: ~SF.isnull(x))).toPandas(),
        )

        # test forall
        self.assert_eq(
            cdf.select(CF.filter(cdf.b, lambda x: x != 0)).toPandas(),
            sdf.select(SF.filter(sdf.b, lambda x: x != 0)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.filter("a", lambda x: ~CF.isnull(x))).toPandas(),
            sdf.select(SF.filter("a", lambda x: ~SF.isnull(x))).toPandas(),
        )

        # test transform
        # transform without index
        self.assert_eq(
            cdf.select(CF.transform(cdf.b, lambda x: x + 1)).toPandas(),
            sdf.select(SF.transform(sdf.b, lambda x: x + 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.transform("b", lambda x: x + 1)).toPandas(),
            sdf.select(SF.transform("b", lambda x: x + 1)).toPandas(),
        )

        # transform with index
        self.assert_eq(
            cdf.select(CF.transform(cdf.b, lambda x, i: x + 1 - i)).toPandas(),
            sdf.select(SF.transform(sdf.b, lambda x, i: x + 1 - i)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.transform("b", lambda x, i: x + 1 - i)).toPandas(),
            sdf.select(SF.transform("b", lambda x, i: x + 1 - i)).toPandas(),
        )

        # test zip_with
        self.assert_eq(
            cdf.select(CF.zip_with(cdf.b, "c", lambda v1, v2: v1 - CF.abs(v2))).toPandas(),
            sdf.select(SF.zip_with(sdf.b, "c", lambda v1, v2: v1 - SF.abs(v2))).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.zip_with("b", cdf.c, lambda v1, v2: v1 - CF.abs(v2))).toPandas(),
            sdf.select(SF.zip_with("b", sdf.c, lambda v1, v2: v1 - SF.abs(v2))).toPandas(),
        )

        # test map_filter
        self.compare_by_show(
            cdf.select(CF.map_filter(cdf.g, lambda k, v: k > v)),
            sdf.select(SF.map_filter(sdf.g, lambda k, v: k > v)),
        )
        self.compare_by_show(
            cdf.select(CF.map_filter("g", lambda k, v: k > v)),
            sdf.select(SF.map_filter("g", lambda k, v: k > v)),
        )

        # test map_zip_with
        self.compare_by_show(
            cdf.select(CF.map_zip_with(cdf.g, "h", lambda k, v1, v2: v1 + v2)),
            sdf.select(SF.map_zip_with(sdf.g, "h", lambda k, v1, v2: v1 + v2)),
        )
        self.compare_by_show(
            cdf.select(CF.map_zip_with("g", cdf.h, lambda k, v1, v2: v1 + v2)),
            sdf.select(SF.map_zip_with("g", sdf.h, lambda k, v1, v2: v1 + v2)),
        )

        # test transform_keys
        self.compare_by_show(
            cdf.select(CF.transform_keys(cdf.g, lambda k, v: k - 1)),
            sdf.select(SF.transform_keys(sdf.g, lambda k, v: k - 1)),
        )
        self.compare_by_show(
            cdf.select(CF.transform_keys("g", lambda k, v: k - 1)),
            sdf.select(SF.transform_keys("g", lambda k, v: k - 1)),
        )

        # test transform_values
        self.compare_by_show(
            cdf.select(CF.transform_values(cdf.g, lambda k, v: CF.abs(v) + 1)),
            sdf.select(SF.transform_values(sdf.g, lambda k, v: SF.abs(v) + 1)),
        )
        self.compare_by_show(
            cdf.select(CF.transform_values("g", lambda k, v: CF.abs(v) + 1)),
            sdf.select(SF.transform_values("g", lambda k, v: SF.abs(v) + 1)),
        )

    def test_csv_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            ('1,2,3', 'a,b,5.0'),
            ('3,4,5', 'x,y,6.0')
            AS tab(a, b)
            """
        # +-----+-------+
        # |    a|      b|
        # +-----+-------+
        # |1,2,3|a,b,5.0|
        # |3,4,5|x,y,6.0|
        # +-----+-------+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # test from_csv
        self.compare_by_show(
            cdf.select(
                CF.from_csv(cdf.a, "a INT, b INT, c INT"),
                CF.from_csv("b", "x STRING, y STRING, z DOUBLE"),
            ),
            sdf.select(
                SF.from_csv(sdf.a, "a INT, b INT, c INT"),
                SF.from_csv("b", "x STRING, y STRING, z DOUBLE"),
            ),
        )
        self.compare_by_show(
            cdf.select(
                CF.from_csv(cdf.a, CF.lit("a INT, b INT, c INT")),
                CF.from_csv("b", CF.lit("x STRING, y STRING, z DOUBLE")),
            ),
            sdf.select(
                SF.from_csv(sdf.a, SF.lit("a INT, b INT, c INT")),
                SF.from_csv("b", SF.lit("x STRING, y STRING, z DOUBLE")),
            ),
        )

        # test schema_of_csv
        self.assert_eq(
            cdf.select(CF.schema_of_csv(CF.lit('{"a": 0}'))).toPandas(),
            sdf.select(SF.schema_of_csv(SF.lit('{"a": 0}'))).toPandas(),
        )

        # test to_csv
        self.compare_by_show(
            cdf.select(CF.to_csv(CF.struct(CF.lit("a"), CF.lit("b")))),
            sdf.select(SF.to_csv(SF.struct(SF.lit("a"), SF.lit("b")))),
        )

    def test_json_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            ('{"a": 1}', '[1, 2, 3]', '{"f1": "value1", "f2": "value2"}'),
            ('{"a": 0}', '[4, 5, 6]', '{"f1": "value12"}')
            AS tab(a, b, c)
            """
        # +--------+---------+--------------------------------+
        # |       a|        b|                               c|
        # +--------+---------+--------------------------------+
        # |{"a": 1}|[1, 2, 3]|{"f1": "value1", "f2": "value2"}|
        # |{"a": 0}|[4, 5, 6]|               {"f1": "value12"}|
        # +--------+---------+--------------------------------+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # test from_json
        for schema in [
            "a INT",
            "MAP<STRING,INT>",
            # StructType([StructField("a", IntegerType())]),
            # ArrayType(StructType([StructField("a", IntegerType())])),
        ]:
            self.compare_by_show(
                cdf.select(CF.from_json(cdf.a, schema)),
                sdf.select(SF.from_json(sdf.a, schema)),
            )
            self.compare_by_show(
                cdf.select(CF.from_json("a", schema)),
                sdf.select(SF.from_json("a", schema)),
            )

        for schema in [
            "ARRAY<INT>",
            # ArrayType(IntegerType()),
        ]:
            self.compare_by_show(
                cdf.select(CF.from_json(cdf.b, schema)),
                sdf.select(SF.from_json(sdf.b, schema)),
            )
            self.compare_by_show(
                cdf.select(CF.from_json("b", schema)),
                sdf.select(SF.from_json("b", schema)),
            )

        # test get_json_object
        self.assert_eq(
            cdf.select(
                CF.get_json_object("c", "$.f1"),
                CF.get_json_object(cdf.c, "$.f2"),
            ).toPandas(),
            sdf.select(
                SF.get_json_object("c", "$.f1"),
                SF.get_json_object(sdf.c, "$.f2"),
            ).toPandas(),
        )

        # test json_tuple
        self.assert_eq(
            cdf.select(CF.json_tuple("c", "f1", "f2")).toPandas(),
            sdf.select(SF.json_tuple("c", "f1", "f2")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.json_tuple(cdf.c, "f1", "f2")).toPandas(),
            sdf.select(SF.json_tuple(sdf.c, "f1", "f2")).toPandas(),
        )

        # test schema_of_json
        self.assert_eq(
            cdf.select(CF.schema_of_json(CF.lit('{"a": 0}'))).toPandas(),
            sdf.select(SF.schema_of_json(SF.lit('{"a": 0}'))).toPandas(),
        )

        # test to_json
        self.compare_by_show(
            cdf.select(CF.to_json(CF.struct(CF.lit("a"), CF.lit("b")))),
            sdf.select(SF.to_json(SF.struct(SF.lit("a"), SF.lit("b")))),
        )

    def test_string_functions_one_arg(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            ('   ab   ', 'ab   ', NULL), ('   ab', NULL, 'ab')
            AS tab(a, b, c)
            """
        # +--------+-----+----+
        # |       a|    b|   c|
        # +--------+-----+----+
        # |   ab   |ab   |null|
        # |      ab| null|  ab|
        # +--------+-----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        for cfunc, sfunc in [
            (CF.upper, SF.upper),
            (CF.lower, SF.lower),
            (CF.ascii, SF.ascii),
            (CF.base64, SF.base64),
            (CF.unbase64, SF.unbase64),
            (CF.ltrim, SF.ltrim),
            (CF.rtrim, SF.rtrim),
            (CF.trim, SF.trim),
            (CF.sentences, SF.sentences),
            (CF.initcap, SF.initcap),
            (CF.soundex, SF.soundex),
            (CF.bin, SF.bin),
            (CF.hex, SF.hex),
            (CF.unhex, SF.unhex),
            (CF.length, SF.length),
            (CF.octet_length, SF.octet_length),
            (CF.bit_length, SF.bit_length),
            (CF.reverse, SF.reverse),
        ]:
            self.assert_eq(
                cdf.select(cfunc("a"), cfunc(cdf.b)).toPandas(),
                sdf.select(sfunc("a"), sfunc(sdf.b)).toPandas(),
            )

    def test_string_functions_multi_args(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (1, 'abcdef', 'ghij', 'hello world', 'a.b.c.d'),
            (2, 'abcd', 'efghij', 'how are you', 'a.b.c')
            AS tab(a, b, c, d, e)
            """
        # +---+------+------+-----------+-------+
        # |  a|     b|     c|          d|      e|
        # +---+------+------+-----------+-------+
        # |  1|abcdef|  ghij|hello world|a.b.c.d|
        # |  2|  abcd|efghij|how are you|  a.b.c|
        # +---+------+------+-----------+-------+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        self.assert_eq(
            cdf.select(CF.format_number(cdf.a, 2)).toPandas(),
            sdf.select(SF.format_number(sdf.a, 2)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.format_number("a", 5)).toPandas(),
            sdf.select(SF.format_number("a", 5)).toPandas(),
        )

        self.assert_eq(
            cdf.select(CF.concat_ws("-", cdf.b, "c")).toPandas(),
            sdf.select(SF.concat_ws("-", sdf.b, "c")).toPandas(),
        )

        self.assert_eq(
            cdf.select(CF.decode("c", "UTF-8")).toPandas(),
            sdf.select(SF.decode("c", "UTF-8")).toPandas(),
        )

        self.assert_eq(
            cdf.select(CF.encode("c", "UTF-8")).toPandas(),
            sdf.select(SF.encode("c", "UTF-8")).toPandas(),
        )

        self.assert_eq(
            cdf.select(CF.format_string("%d %s", cdf.a, cdf.b)).toPandas(),
            sdf.select(SF.format_string("%d %s", sdf.a, sdf.b)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.instr(cdf.b, "b")).toPandas(), sdf.select(SF.instr(sdf.b, "b")).toPandas()
        )
        self.assert_eq(
            cdf.select(CF.overlay(cdf.b, cdf.c, 2)).toPandas(),
            sdf.select(SF.overlay(sdf.b, sdf.c, 2)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.substring(cdf.b, 1, 2)).toPandas(),
            sdf.select(SF.substring(sdf.b, 1, 2)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.substring_index(cdf.e, ".", 2)).toPandas(),
            sdf.select(SF.substring_index(sdf.e, ".", 2)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.levenshtein(cdf.b, cdf.c)).toPandas(),
            sdf.select(SF.levenshtein(sdf.b, sdf.c)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.locate("e", cdf.b)).toPandas(),
            sdf.select(SF.locate("e", sdf.b)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.lpad(cdf.b, 10, "#")).toPandas(),
            sdf.select(SF.lpad(sdf.b, 10, "#")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.rpad(cdf.b, 10, "#")).toPandas(),
            sdf.select(SF.rpad(sdf.b, 10, "#")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.repeat(cdf.b, 2)).toPandas(), sdf.select(SF.repeat(sdf.b, 2)).toPandas()
        )
        self.assert_eq(
            cdf.select(CF.split(cdf.b, "[bd]")).toPandas(),
            sdf.select(SF.split(sdf.b, "[bd]")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.regexp_extract(cdf.b, "(a+)(b)?(c)", 1)).toPandas(),
            sdf.select(SF.regexp_extract(sdf.b, "(a+)(b)?(c)", 1)).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.regexp_replace(cdf.b, "(a+)(b)?(c)", "--")).toPandas(),
            sdf.select(SF.regexp_replace(sdf.b, "(a+)(b)?(c)", "--")).toPandas(),
        )
        self.assert_eq(
            cdf.select(CF.translate(cdf.b, "abc", "xyz")).toPandas(),
            sdf.select(SF.translate(sdf.b, "abc", "xyz")).toPandas(),
        )

    # TODO(SPARK-41283): To compare toPandas for test cases with dtypes marked
    def test_date_ts_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            ('1997/02/28 10:30:00', '2023/03/01 06:00:00', 'JST', 1428476400, 2020, 12, 6),
            ('2000/01/01 04:30:05', '2020/05/01 12:15:00', 'PST', 1403892395, 2022, 12, 6)
            AS tab(ts1, ts2, tz, seconds, Y, M, D)
            """
        # +-------------------+-------------------+---+----------+----+---+---+
        # |                ts1|                ts2| tz|   seconds|   Y|  M|  D|
        # +-------------------+-------------------+---+----------+----+---+---+
        # |1997/02/28 10:30:00|2023/03/01 06:00:00|JST|1428476400|2020| 12|  6|
        # |2000/01/01 04:30:05|2020/05/01 12:15:00|PST|1403892395|2022| 12|  6|
        # +-------------------+-------------------+---+----------+----+---+---+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # With no parameters
        for cfunc, sfunc in [
            (CF.current_date, SF.current_date),
        ]:
            self.assert_eq(
                cdf.select(cfunc()).toPandas(),
                sdf.select(sfunc()).toPandas(),
            )

        # current_timestamp
        # [left]:  datetime64[ns, America/Los_Angeles]
        # [right]: datetime64[ns]
        # TODO: compare the return values after resolving dtypes difference
        self.assertEqual(
            cdf.select(CF.current_timestamp()).count(),
            sdf.select(SF.current_timestamp()).count(),
        )

        # localtimestamp
        s_pdf0 = sdf.select(SF.localtimestamp()).toPandas()
        c_pdf = cdf.select(CF.localtimestamp()).toPandas()
        s_pdf1 = sdf.select(SF.localtimestamp()).toPandas()
        self.assert_eq(s_pdf0 < c_pdf, c_pdf < s_pdf1)

        # With only column parameter
        for cfunc, sfunc in [
            (CF.year, SF.year),
            (CF.quarter, SF.quarter),
            (CF.month, SF.month),
            (CF.dayofweek, SF.dayofweek),
            (CF.dayofmonth, SF.dayofmonth),
            (CF.dayofyear, SF.dayofyear),
            (CF.hour, SF.hour),
            (CF.minute, SF.minute),
            (CF.second, SF.second),
            (CF.weekofyear, SF.weekofyear),
            (CF.last_day, SF.last_day),
            (CF.unix_timestamp, SF.unix_timestamp),
        ]:
            self.assert_eq(
                cdf.select(cfunc(cdf.ts1)).toPandas(),
                sdf.select(sfunc(sdf.ts1)).toPandas(),
            )

        # With format parameter
        for cfunc, sfunc in [
            (CF.date_format, SF.date_format),
            (CF.to_date, SF.to_date),
        ]:
            self.assert_eq(
                cdf.select(cfunc(cdf.ts1, format="yyyy-MM-dd")).toPandas(),
                sdf.select(sfunc(sdf.ts1, format="yyyy-MM-dd")).toPandas(),
            )
        self.compare_by_show(
            # [left]:  datetime64[ns, America/Los_Angeles]
            # [right]: datetime64[ns]
            cdf.select(CF.to_timestamp(cdf.ts1, format="yyyy-MM-dd")),
            sdf.select(SF.to_timestamp(sdf.ts1, format="yyyy-MM-dd")),
        )

        # With tz parameter
        for cfunc, sfunc in [
            (CF.from_utc_timestamp, SF.from_utc_timestamp),
            (CF.to_utc_timestamp, SF.to_utc_timestamp),
            # [left]:  datetime64[ns, America/Los_Angeles]
            # [right]: datetime64[ns]
        ]:
            self.compare_by_show(
                cdf.select(cfunc(cdf.ts1, tz=cdf.tz)),
                sdf.select(sfunc(sdf.ts1, tz=sdf.tz)),
            )

        # With numeric parameter
        for cfunc, sfunc in [
            (CF.date_add, SF.date_add),
            (CF.date_sub, SF.date_sub),
            (CF.add_months, SF.add_months),
        ]:
            self.assert_eq(
                cdf.select(cfunc(cdf.ts1, cdf.D)).toPandas(),
                sdf.select(sfunc(sdf.ts1, sdf.D)).toPandas(),
            )

        # With another timestamp as parameter
        for cfunc, sfunc in [
            (CF.datediff, SF.datediff),
            (CF.months_between, SF.months_between),
        ]:
            self.assert_eq(
                cdf.select(cfunc(cdf.ts1, cdf.ts2)).toPandas(),
                sdf.select(sfunc(sdf.ts1, sdf.ts2)).toPandas(),
            )

        # With seconds parameter
        self.compare_by_show(
            # [left]:  datetime64[ns, America/Los_Angeles]
            # [right]: datetime64[ns]
            cdf.select(CF.timestamp_seconds(cdf.seconds)),
            sdf.select(SF.timestamp_seconds(sdf.seconds)),
        )

        # make_date
        self.assert_eq(
            cdf.select(CF.make_date(cdf.Y, cdf.M, cdf.D)).toPandas(),
            sdf.select(SF.make_date(sdf.Y, sdf.M, sdf.D)).toPandas(),
        )

        # date_trunc
        self.compare_by_show(
            # [left]:  datetime64[ns, America/Los_Angeles]
            # [right]: datetime64[ns]
            cdf.select(CF.date_trunc("day", cdf.ts1)),
            sdf.select(SF.date_trunc("day", sdf.ts1)),
        )

        # trunc
        self.assert_eq(
            cdf.select(CF.trunc(cdf.ts1, "year")).toPandas(),
            sdf.select(SF.trunc(sdf.ts1, "year")).toPandas(),
        )

        # next_day
        self.assert_eq(
            cdf.select(CF.next_day(cdf.ts1, "Mon")).toPandas(),
            sdf.select(SF.next_day(sdf.ts1, "Mon")).toPandas(),
        )

    def test_time_window_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT * FROM VALUES
            (TIMESTAMP('2022-12-25 10:30:00'), 1),
            (TIMESTAMP('2022-12-25 10:31:00'), 2),
            (TIMESTAMP('2022-12-25 10:32:00'), 1),
            (TIMESTAMP('2022-12-25 10:33:00'), 2),
            (TIMESTAMP('2022-12-26 09:30:00'), 1),
            (TIMESTAMP('2022-12-26 09:35:00'), 3)
            AS tab(date, val)
            """

        # +-------------------+---+
        # |               date|val|
        # +-------------------+---+
        # |2022-12-25 10:30:00|  1|
        # |2022-12-25 10:31:00|  2|
        # |2022-12-25 10:32:00|  1|
        # |2022-12-25 10:33:00|  2|
        # |2022-12-26 09:30:00|  1|
        # |2022-12-26 09:35:00|  3|
        # +-------------------+---+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # test window
        self.compare_by_show(
            cdf.select(CF.window("date", "15 seconds")),
            sdf.select(SF.window("date", "15 seconds")),
            truncate=100,
        )
        self.compare_by_show(
            cdf.select(CF.window(cdf.date, "1 minute")),
            sdf.select(SF.window(sdf.date, "1 minute")),
            truncate=100,
        )

        self.compare_by_show(
            cdf.select(CF.window("date", "15 seconds", "5 seconds")),
            sdf.select(SF.window("date", "15 seconds", "5 seconds")),
            truncate=100,
        )
        self.compare_by_show(
            cdf.select(CF.window(cdf.date, "1 minute", "10 seconds")),
            sdf.select(SF.window(sdf.date, "1 minute", "10 seconds")),
            truncate=100,
        )

        self.compare_by_show(
            cdf.select(CF.window("date", "15 seconds", "10 seconds", "5 seconds")),
            sdf.select(SF.window("date", "15 seconds", "10 seconds", "5 seconds")),
            truncate=100,
        )
        self.compare_by_show(
            cdf.select(CF.window(cdf.date, "1 minute", "10 seconds", "5 seconds")),
            sdf.select(SF.window(sdf.date, "1 minute", "10 seconds", "5 seconds")),
            truncate=100,
        )

        # test session_window
        self.compare_by_show(
            cdf.select(CF.session_window("date", "15 seconds")),
            sdf.select(SF.session_window("date", "15 seconds")),
            truncate=100,
        )
        self.compare_by_show(
            cdf.select(CF.session_window(cdf.date, "1 minute")),
            sdf.select(SF.session_window(sdf.date, "1 minute")),
            truncate=100,
        )

        # test window_time
        self.compare_by_show(
            cdf.groupBy(CF.window("date", "5 seconds"))
            .agg(CF.sum("val").alias("sum"))
            .select(CF.window_time("window")),
            sdf.groupBy(SF.window("date", "5 seconds"))
            .agg(SF.sum("val").alias("sum"))
            .select(SF.window_time("window")),
            truncate=100,
        )

    def test_misc_functions(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT a, b, c, BINARY(c) as d FROM VALUES
            (0, float("NAN"), 'x'), (1, NULL, 'y'), (1, 2.1, 'z'), (0, 0.5, NULL)
            AS tab(a, b, c)
            """
        # +---+----+----+----+
        # |  a|   b|   c|   d|
        # +---+----+----+----+
        # |  0| NaN|   x|[78]|
        # |  1|null|   y|[79]|
        # |  1| 2.1|   z|[7A]|
        # |  0| 0.5|null|null|
        # +---+----+----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        # test assert_true
        with self.assertRaises(grpc.RpcError):
            cdf.select(CF.assert_true(cdf.a > 0, "a should be positive!")).show()

        # test raise_error
        with self.assertRaises(grpc.RpcError):
            cdf.select(CF.raise_error("a should be positive!")).show()

        # test crc32
        self.assert_eq(
            cdf.select(CF.crc32(cdf.d)).toPandas(),
            sdf.select(SF.crc32(sdf.d)).toPandas(),
        )

        # test hash
        self.assert_eq(
            cdf.select(CF.hash(cdf.a, "b", cdf.c)).toPandas(),
            sdf.select(SF.hash(sdf.a, "b", sdf.c)).toPandas(),
        )

        # test xxhash64
        self.assert_eq(
            cdf.select(CF.xxhash64(cdf.a, "b", cdf.c)).toPandas(),
            sdf.select(SF.xxhash64(sdf.a, "b", sdf.c)).toPandas(),
        )

        # test md5
        self.assert_eq(
            cdf.select(CF.md5(cdf.d), CF.md5("c")).toPandas(),
            sdf.select(SF.md5(sdf.d), SF.md5("c")).toPandas(),
        )

        # test sha1
        self.assert_eq(
            cdf.select(CF.sha1(cdf.d), CF.sha1("c")).toPandas(),
            sdf.select(SF.sha1(sdf.d), SF.sha1("c")).toPandas(),
        )

        # test sha2
        self.assert_eq(
            cdf.select(CF.sha2(cdf.c, 256), CF.sha2("d", 512)).toPandas(),
            sdf.select(SF.sha2(sdf.c, 256), SF.sha2("d", 512)).toPandas(),
        )

    def test_call_udf(self):
        from pyspark.sql import functions as SF
        from pyspark.sql.connect import functions as CF

        query = """
            SELECT a, b, c, BINARY(c) as d FROM VALUES
            (-1.0, float("NAN"), 'x'), (-2.1, NULL, 'y'), (1, 2.1, 'z'), (0, 0.5, NULL)
            AS tab(a, b, c)
            """

        # +----+----+----+----+
        # |   a|   b|   c|   d|
        # +----+----+----+----+
        # |-1.0| NaN|   x|[78]|
        # |-2.1|null|   y|[79]|
        # | 1.0| 2.1|   z|[7A]|
        # | 0.0| 0.5|null|null|
        # +----+----+----+----+

        cdf = self.connect.sql(query)
        sdf = self.spark.sql(query)

        self.assert_eq(
            cdf.select(
                CF.call_udf("abs", cdf.a), CF.call_udf("xxhash64", "b", cdf.c, "d")
            ).toPandas(),
            sdf.select(
                SF.call_udf("abs", sdf.a), SF.call_udf("xxhash64", "b", sdf.c, "d")
            ).toPandas(),
        )


if __name__ == "__main__":
    import os
    from pyspark.sql.tests.connect.test_connect_function import *  # noqa: F401

    # TODO(SPARK-41547): Enable ANSI mode in this file.
    os.environ["SPARK_ANSI_SQL_MODE"] = "false"

    try:
        import xmlrunner  # type: ignore

        testRunner = xmlrunner.XMLTestRunner(output="target/test-reports", verbosity=2)
    except ImportError:
        testRunner = None
    unittest.main(testRunner=testRunner, verbosity=2)
